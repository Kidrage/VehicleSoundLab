"""Compile saved single-state designs into immutable, source-free V9 banks."""
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import tempfile
import uuid

from research_archive_v1 import sha
from vehicle_controller import dna_bank as dna
from . import models
from .vehicle_system import VehicleSystem, validate as validate_system

GROUPS = ('base', 'idle', 'power', 'overrun')
SCHEMA = 'vsl.workbench-state-recipe/1'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


def identity(value):
    if not isinstance(value, str) or re.fullmatch('[0-9a-f]{32}', value) is None:
        raise ValueError('无效车辆DNA编号')
    return value


class StateRecipes:
    def __init__(self, workspace):
        self.workspace = workspace
        self.root = workspace.root/'state_recipes'
        self.root.mkdir(exist_ok=True)
        self.system = VehicleSystem(workspace)

    def choices(self):
        result = []
        for path in sorted(self.workspace.root.glob('*/project.json'), key=lambda p: p.stat().st_mtime, reverse=True):
            project = read(path)
            if not (path.parent/'base.model').is_file():
                continue
            info = dna.describe((path.parent/'base.model').read_text(encoding='ascii'))
            result.append(dict(id=path.parent.name, name=project['name'], state=project['state'],
                               viewpoint=project['viewpoint'], **info))
        return result

    def listing(self):
        return [dict(id=p.parent.name, **read(p)) for p in sorted(self.root.glob('*/recipe.json'),
                    key=lambda p: p.stat().st_mtime, reverse=True)]

    def configuration(self, data):
        keys = {'name', 'groups', 'reference_rpm', 'transition_seconds', 'detail', 'seed'}
        if not isinstance(data, dict) or not keys <= set(data) or set(data)-keys-{'system'}:
            raise ValueError('车辆DNA配置字段不完整')
        if not isinstance(data['name'], str) or not 1 <= len(data['name'].strip()) <= 100:
            raise ValueError('车辆DNA名称需1–100字')
        groups = data['groups']
        if not isinstance(groups, dict) or set(groups) != set(GROUPS):
            raise ValueError('需要默认、怠速、给油、收油四组')
        for group, values in groups.items():
            if not isinstance(values, list) or not (1 if group == 'base' else 0) <= len(values) <= 8:
                raise ValueError('默认组需1–8个工程，其他组可为空且最多8个')
            if len(set(identity(x) for x in values)) != len(values):
                raise ValueError('同一组不能重复加入同一个工程')
        for key, low, high in (('reference_rpm', 50, 10000), ('transition_seconds', .02, 2.6), ('detail', 0, 1.3)):
            dna._number(data[key], low, high, key)
        dna._integer(data['seed'], 1, 2**32-1, '随机种子')
        result = deepcopy(data)
        if 'system' in data: result['system'] = validate_system(data['system'])
        return result

    def compile(self, config):
        groups, provenance, bindings = {}, {}, {}
        with tempfile.TemporaryDirectory(prefix='vsl-state-recipe-') as temporary:
            for group in GROUPS:
                values = []
                for project_id in config['groups'][group]:
                    folder = self.workspace.folder(project_id)
                    source_hash, model_hash = sha(folder/'project.json'), sha(folder/'base.model')
                    project = read(folder/'project.json')
                    original, root = models.read(folder/'base.model')
                    controls = models.controls(project['params'])
                    edited = models.edit(original, root, controls, project.get('rows'), project.get('rho'))
                    target = Path(temporary)/'voice.model'
                    models.write(target, edited, root)
                    anchor = dna.anchor(target.read_text(encoding='ascii'), project['name'])
                    row = dict(project=project_id, project_sha256=source_hash, base_model_sha256=model_hash,
                        compiled_model_sha256=anchor['sha256'], name=project['name'], state=project['state'],
                        viewpoint=project['viewpoint'], controls=controls, source=project.get('source'),
                        selection=project.get('selection'), model_reference=project.get('model_reference'))
                    values.append((anchor, row));bindings[project_id] = (source_hash, model_hash)
                values.sort(key=lambda x: x[0]['base_hz'])
                groups[group] = [a for a, _ in values];provenance[group] = [p for _, p in values]
        viewpoints = {p['viewpoint'] for rows in provenance.values() for p in rows}
        if len(viewpoints) > 1:
            raise ValueError('各组工程需使用同一录音视角；请分别建立车内、车外配方')
        bank = dna.create(groups['base'], config['reference_rpm'], config['name'], config['seed'], 12, config['detail'])
        bank = dna.with_states(bank, {g: groups[g] for g in dna.STATES if groups[g]}, config['transition_seconds'])
        config = deepcopy(config)
        config['groups'] = {g: [p['project'] for p in provenance[g]] for g in GROUPS}
        # Every input remains owned by its single-state project; external edits
        # during compilation must not silently combine different revisions.
        for project_id, (source_hash, model_hash) in bindings.items():
            folder = self.workspace.folder(project_id)
            if sha(folder/'project.json') != source_hash or sha(folder/'base.model') != model_hash:
                raise ValueError('编译期间来源工程发生变化，请重新保存')
        report = dict(schema='vsl.state-recipe-provenance/1', groups=provenance,
            dna_bank_sha256=dna.digest(bank), configuration=config,
            mapping='User-supplied common acoustic-root/RPM mapping, not measured ECU RPM.',
            parameters='Saved workbench EQ/gain/width/shared/local baked once; preview pitch excluded. Detail and seed are common recipe controls.',
            isolation='Native dry stems only; no renderer. Optional catalog layers/events are not inherited.',
            calibration='Manual state assignment is not evidence of measured RPM/load or physical source separation.')
        return config, bank, report

    def save(self, data):
        if not isinstance(data, dict) or set(data) != {'id', 'configuration'}:
            raise ValueError('车辆DNA保存请求字段错误')
        recipe_id = identity(data['id']) if data['id'] is not None else uuid.uuid4().hex
        folder = self.root/recipe_id
        if data['id'] is not None and not (folder/'recipe.json').is_file():
            raise ValueError('车辆DNA不存在')
        # Finish parameter validation/compilation before creating a new revision.
        config, bank, provenance = self.compile(self.configuration(data['configuration']))
        preset = None
        if 'system' in config:
            preset, provenance['system'] = self.system.compile(bank, config['system'])
        version = uuid.uuid4().hex
        output = folder/version
        output.mkdir(parents=True, exist_ok=False)
        write(output/'vehicle.dnabank.json', bank)
        write(output/'provenance.json', provenance)
        snapshot = dict(schema=SCHEMA, name=config['name'], version=version,
            created=datetime.now(timezone.utc).isoformat(), configuration=config,
            bank_file_sha256=sha(output/'vehicle.dnabank.json'), provenance_file_sha256=sha(output/'provenance.json'))
        if preset is not None:
            write(output/'vehicle.preset.json', preset)
            snapshot['preset_file_sha256'] = sha(output/'vehicle.preset.json')
        write(output/'snapshot.json', snapshot)
        pending = folder/'recipe.pending.json'
        write(pending, dict(schema=SCHEMA, name=config['name'], last_version=version))
        pending.replace(folder/'recipe.json')
        return self.view(recipe_id)

    def view(self, recipe_id, version=None):
        recipe_id = identity(recipe_id);folder = self.root/recipe_id
        current = read(folder/'recipe.json')
        version = identity(version or current['last_version'])
        output = folder/version;snapshot = read(output/'snapshot.json')
        bank_path, source_path = output/'vehicle.dnabank.json', output/'provenance.json'
        if sha(bank_path) != snapshot['bank_file_sha256'] or sha(source_path) != snapshot['provenance_file_sha256']:
            raise ValueError('车辆DNA快照校验失败')
        bank = dna.validate(read(bank_path));sources = read(source_path)
        if dna.digest(bank) != sources['dna_bank_sha256']:
            raise ValueError('车辆DNA参数与来源记录不符')
        self.configuration(snapshot['configuration'])
        if snapshot['configuration'] != sources['configuration']:
            raise ValueError('车辆DNA配置与来源记录不符')
        preset = None
        if 'preset_file_sha256' in snapshot:
            if sha(output/'vehicle.preset.json') != snapshot['preset_file_sha256']:
                raise ValueError('整车参数快照校验失败')
            preset = read(output/'vehicle.preset.json')
            if preset.get('dna_bank') != bank or preset.get('source_effective_sha256') != sources['system']['source_effective_sha256']:
                raise ValueError('整车参数与DNA或来源记录不符')
        changed = []
        for rows in sources['groups'].values():
            for row in rows:
                project = self.workspace.folder(row['project'])
                if (not (project/'project.json').is_file() or not (project/'base.model').is_file() or
                    sha(project/'project.json') != row['project_sha256'] or sha(project/'base.model') != row['base_model_sha256']):
                    changed.append(row['project'])
        prefix = f'/files/state_recipes/{recipe_id}/{version}/'
        versions = [dict(version=p.parent.name, name=v['name'], created=v['created'])
                    for p in sorted(folder.glob('*/snapshot.json'), reverse=True) if (v := read(p))]
        versions.sort(key=lambda x: x['created'], reverse=True)
        result = dict(id=recipe_id, name=snapshot['name'], version=version, configuration=snapshot['configuration'],
            bank=prefix+'vehicle.dnabank.json', provenance=prefix+'provenance.json',
            dna_bank_sha256=dna.digest(bank), coverage=dna.coverage(bank),
            changed_sources=sorted(set(changed)), versions=versions, latest_version=current['last_version'])
        if preset is not None:
            result.update(preset=prefix+'vehicle.preset.json', changed_events=self.system.changed(sources['system']),
                system_notes=sources['system']['notes'])
        return result

"""Verify state assembly, immutable edits/history and actual V9 C adoption."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import traceback
import numpy as np
from sound_designer.workspace import Workspace
from sound_designer.state_recipes import StateRecipes
from sound_designer import models
from vehicle_controller import dna_bank as dna
from vehicle_controller.native import Bridge, Engine
from research_archive_v1 import sha, save


def refused(action):
    try:
        action()
    except (ValueError, FileNotFoundError):
        return
    raise AssertionError('Expected rejection')


def digest_tree(root):
    return {p.relative_to(root).as_posix(): sha(p) for p in root.rglob('*') if p.is_file()}


def binding(repo, output):
    names = ['tools/sound_designer/server.py', 'tools/sound_designer/state_recipes.py',
        'tools/sound_designer/workspace.py', 'tools/sound_designer/models.py',
        'tools/sound_designer/web/index.html', 'tools/sound_designer/web/vehicles.html',
        'tools/sound_designer/web/vehicles.js', 'tools/sound_designer/web/vehicles.css',
        'tools/sound_designer/web/navigation.css',
        'tools/vehicle_controller/dna_bank.py', 'tools/verify_state_recipe_workbench_v1.py']
    sources = {}
    for name in names:
        target = output/'exact_sources'/name;target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(repo/name, target);sources[name] = sha(target)
    save(output/'source_binding.json', sources)


def fixtures(workspace):
    result = {}
    for name, root, high, viewpoint in (
        ('base_low', 40., 0, 'exterior'), ('base_high', 50., 0, 'exterior'),
        ('idle', 44., -3, 'exterior'), ('power', 55., 2, 'exterior'),
        ('overrun', 46., -2, 'exterior'), ('cabin', 45., 0, 'cabin')):
        p = workspace.create(dict(preset='v10', name=name, viewpoint=viewpoint))
        folder = workspace.folder(p['id']);model, _ = models.read(folder/'base.model')
        models.write(folder/'base.model', model, root)
        controls = dict(models.DEFAULTS, high_db=high, gain_db=-8, pitch=1.07)
        workspace.save_design(dict(id=p['id'], name=name, params=controls, rows=None, rho=None))
        result[name] = p['id']
    return result


def manual_bank(workspace, config):
    groups = {}
    with tempfile.TemporaryDirectory() as temporary:
        for group, ids in config['groups'].items():
            groups[group] = []
            for project_id in ids:
                folder, p = workspace.load(project_id);m, root = models.read(folder/'base.model')
                m = models.edit(m, root, models.controls(p['params']), p['rows'], p['rho'])
                path = Path(temporary)/'manual.model';models.write(path, m, root)
                groups[group].append(dna.anchor(path.read_text(encoding='ascii'), p['name']))
            groups[group].sort(key=lambda a: a['base_hz'])
    return dna.with_states(dna.create(groups['base'], config['reference_rpm'], config['name'],
        config['seed'], 12, config['detail']), {g: groups[g] for g in dna.STATES if groups[g]}, config['transition_seconds'])


def run(output):
    output.mkdir(parents=True, exist_ok=False);repo = Path(__file__).resolve().parents[1]
    shutil.copy2(__file__, output/'executed_verification.py');binding(repo, output)
    workspace = Workspace(repo, output/'projects');recipes = StateRecipes(workspace);ids = fixtures(workspace)
    save(output/'fixture_ids.json', ids)
    config = dict(name='四状态工具核查 · 人工声纹', groups=dict(base=[ids['base_high'], ids['base_low']],
        idle=[ids['idle']], power=[ids['power']], overrun=[ids['overrun']]),
        reference_rpm=3000., transition_seconds=.12, detail=.65, seed=48271)
    original_projects = {p: digest_tree(workspace.folder(p)) for p in ids.values()}
    first = recipes.save(dict(id=None, configuration=config))
    bank_file = workspace.root/first['bank'].removeprefix('/files/');bank = dna.read(bank_file)
    expected = manual_bank(workspace, config)
    assert bank == expected and len(recipes.choices()) == 6
    assert [a['base_hz'] for a in bank['anchors']] == [40., 50.]
    assert not first['changed_sources'] and bank['schema'] == dna.STATE_SCHEMA
    assert all(digest_tree(workspace.folder(p)) == original_projects[p] for p in ids.values())
    before = digest_tree(recipes.root);invalid = []
    for key, value in (('reference_rpm', 0), ('reference_rpm', float('nan')), ('detail', True),
                       ('seed', 0), ('transition_seconds', .01)):
        bad = deepcopy(config);bad[key] = value;invalid.append(bad)
    bad = deepcopy(config);bad['groups']['base'] = [];invalid.append(bad)
    bad = deepcopy(config);bad['groups']['idle'] = [ids['idle']]*2;invalid.append(bad)
    bad = deepcopy(config);bad['groups']['power'] = [ids['cabin']];invalid.append(bad)
    for bad in invalid:
        refused(lambda: recipes.save(dict(id=first['id'], configuration=bad)))
        assert digest_tree(recipes.root) == before
    p = workspace.create(dict(preset='warm', name='different-harmonics'))
    bad = deepcopy(config);bad['groups']['power'] = [p['id']]
    refused(lambda: recipes.save(dict(id=first['id'], configuration=bad)))
    assert digest_tree(recipes.root) == before
    folder, project = workspace.load(ids['power']);project['params']['high_db'] = -5
    workspace.save_design(dict(id=ids['power'], name=project['name'], params=project['params'], rows=None, rho=None))
    stale = recipes.view(first['id']);assert stale['changed_sources'] == [ids['power']]
    assert sha(bank_file) == before[bank_file.relative_to(recipes.root).as_posix()]
    second = recipes.save(dict(id=first['id'], configuration=config))
    assert second['version'] != first['version'] and not second['changed_sources'] and len(second['versions']) == 2
    assert recipes.view(first['id'], first['version'])['dna_bank_sha256'] == dna.digest(bank)
    bridge = Bridge(repo);checks = []
    for rpm, load in ((850., 0.), (4000., .7), (4000., -.3)):
        captures = []
        for value in (bank, expected):
            with Engine(bridge, 0, dna_bank=value) as e:
                e.set(dict(e.controls, mode=0, rpm=rpm, load=load, ignition=1, start_id=1))
                pcm = b''.join(e.process(480) for _ in range(200))
                assert np.isfinite(np.frombuffer(pcm, dtype='<f4')).all()
                captures.append((pcm, e.dna_state()))
        assert captures[0] == captures[1]
        checks.append(dict(rpm=rpm, load=load, pcm_sha256=hashlib.sha256(captures[0][0]).hexdigest(), native_exact=True))
    target = workspace.root/first['provenance'].removeprefix('/files/');source_bytes = target.read_bytes()
    target.write_bytes(source_bytes+b' ')
    refused(lambda: recipes.view(first['id'], first['version']));target.write_bytes(source_bytes)
    save(output/'report.json', dict(result='passed', schema='vsl.state-recipe-workbench-verification/1',
        fixture_ids=ids, first=first, second=second, actual_native_C=checks, invalid_preserves_recipe=len(invalid)+1,
        no_source_project_mutation=True, current_saved_edits_exact=True, explicit_preview_pitch_excluded=True,
        sorted_multi_anchor=True, immutable_stale_history=True, tamper_refused=True,
        bridge_sha256=bridge.sha256, new_timbre_accepted=False, goal_complete=False))
    print(json.dumps(dict(result='passed', native_cases=len(checks))), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__);p.add_argument('--output', type=Path, required=True);args = p.parse_args()
    try:
        run(args.output)
    except Exception:
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output/'failure.txt').write_text(traceback.format_exc(), encoding='utf-8')
        raise

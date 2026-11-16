"""Repeatable single-clip jobs over the same workspace/compiler/C preview as UI."""
import base64
import csv
import hashlib
import json
import math
from pathlib import Path
import shutil
import sys

from .metadata import fields
from .models import controls
from .workspace import Workspace


KEYS = {'schema', 'name', 'audio', 'source_sha256', 'state', 'viewpoint', 'selection',
        'root_hz', 'harmonics', 'components', 'allow_unstable', 'parameters'}


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('JSON字段重复：' + key)
        result[key] = value
    return result


def _number(value, low, high, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(label + '超出范围')
    return value


def load(path, raw=None):
    path = Path(path).resolve()
    data = json.loads((path.read_bytes() if raw is None else raw).decode('utf-8-sig'), object_pairs_hook=_object)
    if not isinstance(data, dict) or data.get('schema') != 'vsl.sound-design-job/1':
        raise ValueError('需要vsl.sound-design-job/1任务文件')
    if set(data) - KEYS:
        raise ValueError('未知任务字段：' + ', '.join(sorted(set(data) - KEYS)))
    if not {'name', 'audio', 'state', 'viewpoint'} <= set(data):
        raise ValueError('任务必须标注name、audio、state和viewpoint')
    labels = fields(data)
    if not isinstance(data['audio'], str) or not data['audio']:
        raise ValueError('audio需为本地音频文件路径')
    audio = (path.parent / data['audio']).resolve()
    if not audio.is_file():
        raise ValueError('找不到音频：' + str(audio))
    selection = data.get('selection', {'start': 0, 'end': None})
    if not isinstance(selection, dict) or set(selection) - {'start', 'end'}:
        raise ValueError('selection只接受start／end秒数')
    start = _number(selection.get('start', 0), 0, 60, '选区起点')
    end = selection.get('end')
    if end is not None:
        _number(end, .4, 60, '选区终点')
        if end - start < .4:
            raise ValueError('选区至少0.4秒')
    root = data.get('root_hz')
    if root is not None:
        _number(root, 5, 1000, '声学基频')
    harmonics = data.get('harmonics', 'auto')
    if harmonics != 'auto' and (type(harmonics) is not int or not 1 <= harmonics <= 320):
        raise ValueError('harmonics需为auto或1–320整数')
    components = data.get('components', 12)
    if type(components) is not int or not 0 <= components <= 16:
        raise ValueError('components需为0–16整数')
    allow = data.get('allow_unstable', False)
    if type(allow) is not bool:
        raise ValueError('allow_unstable需为布尔值true／false')
    expected = data.get('source_sha256')
    if expected is not None and (not isinstance(expected, str) or len(expected) != 64 or any(c not in '0123456789abcdefABCDEF' for c in expected)):
        raise ValueError('source_sha256需为64位十六进制哈希或null')
    return dict(schema='vsl.sound-design-job/1', **labels, audio=str(audio),
                source_sha256=expected.lower() if expected else None, selection=dict(start=start, end=end),
                root_hz=root, harmonics=harmonics, components=components, allow_unstable=allow,
                parameters=controls(data.get('parameters', {})))


def _save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8', newline='\n')


def _csv(path, rows, columns):
    with path.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def _toolchain(repo):
    import numpy
    import scipy
    import soundfile
    source = list((repo / 'tools/sound_designer').glob('*.py'))
    source += [repo / 'tools/design_sound_clip.py', repo / 'tools/sound_dna/profile.py', repo / 'tools/sound_dna/statistics.py']
    return dict(schema='vsl.sound-design-toolchain/1', python=sys.version,
                numpy=numpy.__version__, scipy=scipy.__version__, soundfile=soundfile.__version__,
                source_sha256={p.relative_to(repo).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(source)})


def execute(repo, data_root, spec, output, inspect=False):
    """New output directory per execution; receipts distinguish analysis and synthesis."""
    raw_job = Path(spec).read_bytes()
    job = load(spec, raw_job)
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    report = dict(schema='vsl.sound-design-job-result/1', status='running', stage='input',
                  job_file=str(Path(spec).resolve()), job_sha256=hashlib.sha256(raw_job).hexdigest(),output=str(output), compiled=False,
                  listening_accepted=False, state=job['state'], viewpoint=job['viewpoint'])
    try:
        (output / 'job.input.json').write_bytes(raw_job)
        _save(output / 'toolchain.json', _toolchain(Path(repo)))
        report['toolchain_sha256'] = hashlib.sha256((output / 'toolchain.json').read_bytes()).hexdigest()
        audio = Path(job['audio'])
        if audio.stat().st_size > 48 * 1024**2:
            raise ValueError('音频文件需小于48MB')
        raw = audio.read_bytes()
        actual = hashlib.sha256(raw).hexdigest()
        report['source_sha256'] = actual
        if job['source_sha256'] and job['source_sha256'] != actual:
            raise ValueError('音频SHA256与任务记录不符；未开始提取')
        job['source_sha256'] = actual
        _save(output / 'job.resolved.json', job)
        workspace = Workspace(Path(repo), Path(data_root) / 'designs')
        p = workspace.create(dict(filename=audio.name, audio=base64.b64encode(raw).decode(),
                                  name=job['name'], state=job['state'], viewpoint=job['viewpoint']))
        report.update(stage='analysis', project_id=p['id'], project_folder=str(workspace.folder(p['id'])),
                      source_sha256=actual, ui_path='/?project=' + p['id'])
        stop = job['selection']['end']
        p = workspace.analyze(dict(id=p['id'], start=job['selection']['start'],
                                   end=p['analysis']['seconds'] if stop is None else stop, root_hz=job['root_hz']))
        a = p['analysis']
        analysis = dict(schema='vsl.sound-designer-analysis/1', reference=a, selection=p['selection'],
                        model_reference=None, reference_matches_model=None)
        _save(output / 'analysis.json', analysis)
        _csv(output / 'pitch_track.csv', a['pitch_track'], ['seconds', 'hz', 'score'])
        _csv(output / 'bands.csv', a['bands'], ['low', 'high', 'power', 'db'])
        report.update(selection=p['selection'], stable_candidate=a['stable_candidate'],
                      root_candidates=a['root_candidates'], pitch_drift=a['pitch_drift'])
        if inspect:
            report.update(status='analyzed', stage='complete', exit_code=0)
        elif job['root_hz'] is None:
            report.update(status='root_confirmation_required', stage='analysis', exit_code=3,
                          reason='分析已保存。确认声学基频后填写root_hz，使用新输出目录重跑；不会静默采用候选值。')
        elif not a['stable_candidate'] and not job['allow_unstable']:
            report.update(status='stable_crop_required', stage='analysis', exit_code=4,
                          reason='缩短为稳定片段，或显式选择allow_unstable=true生成固定音色草稿。')
        else:
            report['stage'] = 'compile'
            h = min(320, math.floor(21600 / (job['root_hz'] * 1.1))) if job['harmonics'] == 'auto' else job['harmonics']
            p = workspace.compile(dict(id=p['id'], root_hz=job['root_hz'], harmonics=h,
                                       components=job['components'], allow_unstable=job['allow_unstable']))
            report.update(stage='C_preview', harmonics=p['model']['harmonics'], components=p['model']['components'],
                          highest_partial_hz=p['model']['root_hz'] * p['model']['harmonics'],
                          fixed_timbre_draft=not a['stable_candidate'],model_scope=p['model_scope'])
            result = workspace.render(dict(id=p['id'], params=job['parameters']))
            version = workspace.folder(p['id']) / result['project']['last_version']
            for name in ('voice.model', 'parameters.json', 'harmonics.csv', 'analysis.json', 'preview.wav', 'sound-design.zip'):
                shutil.copy2(version / name, output / name)
            report.update(status='generated', stage='complete', compiled=True, exit_code=0,
                          render_report=result['project']['render_report'])
        report['output_sha256'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in output.iterdir() if p.is_file()}
    except Exception as error:
        report.update(status='failed', error=str(error), exit_code=2)
    _save(output / 'receipt.json', report)
    return report

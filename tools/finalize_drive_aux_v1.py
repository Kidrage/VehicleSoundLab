"""Bind driving auxiliary evidence, exports and a shared-gain listening page."""
import argparse
import csv
import hashlib
import html
import json
from pathlib import Path
import shutil
import subprocess
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace', type=Path, required=True)
args = parser.parse_args()
repo = Path(__file__).resolve().parents[1]
root = args.workspace / 'references/analysis/drive_aux_v1'
verified = root / 'verification2'
sys.path.insert(0, str(args.workspace / 'tools/python_deps'))
import numpy as np
import soundfile as sf


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


offline = json.loads((verified / 'verification.json').read_text(encoding='utf-8'))
assert offline['result'] == 'pass'
documentation_updates = []
for name, digest in offline['source_sha256'].items():
    assert sha(verified / 'exact_sources' / name) == digest, name
    if sha(repo / name) != digest:
        assert Path(name).suffix == '.md', name
        documentation_updates.append(name)
initial_log = (root / 'LastTest-initial.log').read_bytes()
focused_log = (root / 'LastTest-focused.log').read_bytes()
assert initial_log.count(b'Test Passed.') == 36 and initial_log.count(b'Test Failed.') == 1
assert focused_log.count(b'Test Passed.') == 1 and b'Test Failed.' not in focused_log
logs = root / 'logs'
logs.mkdir(exist_ok=False)
for log in sorted((args.workspace / 'references/analysis').glob('drive_aux_v1_build_attempt*.log')):
    shutil.copy2(log, logs / log.name)
device = json.loads((root / 'device/设备 行程.vslrun.json').read_text(encoding='utf-8'))
assert device['verified'] and device['rejected_block_excluded'] and device['frames'] == 144123
assert device['record_hash'] == device['play_hash']
for prefix in ('record', 'play'):
    assert device[prefix + '_queue_empty'] == device[prefix + '_over_budget'] == 0
    assert abs(device[prefix + '_device_seconds'] - device['frames'] / 48000) < .06

isolated = root / 'device/without-models'
isolated.mkdir(exist_ok=False)
exports = []
for channels in (2, 12):
    command = [str(repo / 'handoff-build/bin/Release/VslAtlasTake_render.exe'),
               str(root / 'device/设备 行程.vslrun'), str(root / f'device/export_{channels}.wav'), '--channels', str(channels)]
    result = subprocess.run(command, cwd=isolated, capture_output=True, text=True, encoding='utf-8', errors='replace')
    assert result.returncode == 0, result.stderr
    record = json.loads(result.stdout)
    assert record['verified'] and record['frames'] == device['frames']
    audio, rate = sf.read(root / f'device/export_{channels}.wav', dtype='float32', always_2d=True)
    assert rate == 48000 and audio.shape == (device['frames'], channels) and np.isfinite(audio).all()
    if channels == 2:
        assert record['audio_hash'] == device['record_hash']
    exports.append(dict(command=command, **record))
assert exports[0]['source_hash'] == exports[1]['source_hash']
(root / 'device/exports.json').write_text(json.dumps(exports, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

review = root / 'review'
review.mkdir(exist_ok=False)
assets = review / 'assets'
assets.mkdir()
tracks = [('base', '原混音', 'DNA＋低频分层＋既有细节与瞬态，新增五层关闭。'),
          ('layers', '加入五路声层', '进气／机械／空气50%，道路／风30%；同一驾驶轨迹。'),
          ('intake', '进气独奏', '工程进气声层，保持完整混音中的电平。'),
          ('mechanical', '机械独奏', '旋转／燃烧机械共振，保持完整混音中的电平。'),
          ('air', '排气空气独奏', '左右气流＋喷油幅度门，保持完整混音中的电平。'),
          ('road', '道路独奏', '车速关联，保持完整混音中的电平。'),
          ('wind', '风声独奏', '车速平方关联，保持完整混音中的电平。')]
for context in ('A', 'E'):
    for name, suffix in [('base', 'zero'), ('layers', 'layers')]:
        shutil.copy2(verified / f'{context}_{suffix}_render.wav', assets / f'{context}_{name}.wav')
    for name in ('intake', 'mechanical', 'road', 'wind'):
        audio, rate = sf.read(verified / f'{context}_layers_{name}.wav', always_2d=True)
        stereo = np.repeat(audio, 2, axis=1) * (.2 / np.sqrt(2))
        sf.write(assets / f'{context}_{name}.wav', stereo, rate, subtype='FLOAT')
    left, rate = sf.read(verified / f'{context}_layers_air_left.wav')
    right, _ = sf.read(verified / f'{context}_layers_air_right.wav')
    sf.write(assets / f'{context}_air.wav', .2 * np.column_stack([left, right]), rate, subtype='FLOAT')


def page(prefix):
    sections = []
    for context, title in [('A', '车外实验库 · 模拟驾驶／换挡／松油／熄火'), ('E', '车内实验库 · 固定高转')]:
        cards = ''.join(f'<article><h3>{html.escape(label)}</h3><p>{html.escape(note)}</p>'
                        f'<audio controls preload="metadata" src="{prefix}{context}_{name}.wav"></audio></article>'
                        for name, label, note in tracks)
        sections.append(f'<section><h2>{title}</h2>{cards}</section>')
    return '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>驾驶声层集成 V1</title><style>
body{margin:0;background:#f3f5f7;color:#15212b;font:16px/1.65 system-ui,"Microsoft YaHei",sans-serif}
main{max-width:850px;margin:32px auto;padding:0 20px}h1{font-size:28px}h2{font-size:22px;margin-top:32px}h3{font-size:18px;margin:0}
article{background:white;border:1px solid #d9e0e6;border-radius:10px;padding:18px;margin:14px 0}p{color:#465562;margin:9px 0}audio{width:100%;margin-top:8px}
</style><main><h1>驾驶声层集成 V1</h1>
<p>先暂停其他发声窗口。先比较两条完整混音，再逐层听；同一主音量，没有逐版增益补偿。独奏可能很轻。</p>
<p>本页验证声层的协作与触发。新增层是可调工程模型，音色尚未听评；A驻车／E车内驾驶库与已认可的A移动尾排固定配方分别保留。</p>
''' + ''.join(sections) + '''<script>const players=[...document.querySelectorAll('audio')];
players.forEach(a=>a.addEventListener('play',()=>players.forEach(b=>{if(a!==b)b.pause()})));</script></main></html>'''


(review / 'index.html').write_text(page('assets/'), encoding='utf-8')
published = args.workspace / 'research/驾驶声层集成V1.html'
assert not published.exists()
published.write_text(page('../references/analysis/drive_aux_v1/review/assets/'), encoding='utf-8')
for path in assets.glob('*.wav'):
    audio, rate = sf.read(path, always_2d=True)
    assert rate == 48000 and audio.shape[1] == 2 and np.isfinite(audio).all() and abs(audio).max() < .95

with (repo / 'handoff/C文件索引.csv').open(encoding='utf-8-sig', newline='') as stream:
    rows = list(csv.DictReader(stream))
for row in rows:
    assert sha(repo / row['文件']) == row['SHA-256'], row['文件']
code = [p for folder in ('drive_aux', 'atlas_drive', 'atlas_take', 'atlas_take_io')
        for p in (repo / 'modules' / folder).iterdir() if p.is_file()]
code += [p for folder in ('drive_aux_v1', 'atlas_monitor_v1', 'atlas_take_v1')
         for p in (repo / 'experiments' / folder).iterdir() if p.is_file()]
code += [repo / 'experiments/atlas_drive_v1/probe.c', repo / 'handoff/CMakeLists.txt', Path(__file__),
         repo / 'tools/verify_drive_aux_v1.py']
summary = dict(schema='vsl.driving-auxiliary-summary/1', date='2026-11-12', result='pass', tests=37,
    human_accepted=False, ui_interaction_verified=False, ui_visual_verified=False,
    base_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip(),
    evidence_root=str(root), recording_schema=2, control_fields=25, device=device, exports=exports,
    zero_equal_stems=offline['zero_equal_stems'], layout_source_invariant=True,
    documentation_updates_after_verification=documentation_updates,
    c_index_rows=len(rows), c_index_sha256=sha(repo / 'handoff/C文件索引.csv'),
    source_sha256={p.relative_to(repo).as_posix(): sha(p) for p in code},
    evidence_sha256={p.relative_to(root).as_posix(): sha(p) for p in sorted(root.rglob('*')) if p.is_file()},
    binary_sha256={name: sha(repo / 'handoff-build/bin/Release' / name) for name in
                   ('VslAtlasMonitor.exe', 'VslAtlasDrive_probe.exe', 'VslAtlasTake_render.exe', 'VslAtlasTake_device_checks.exe')},
    unchanged_accepted_models={p.relative_to(repo).as_posix(): sha(p) for folder in ('dna_bank_v1', 'coherent_low_v1')
                               for p in (repo / 'voices' / folder).glob('*.model')},
    limits=['Engineering auxiliary templates, not physical source separation or state-colour calibration',
            'A4/E2 driving voices remain unaccepted; accepted moving A pair stays separate',
            'Offline240frame overruns persist; short muted device pass is not hard realtime',
            'Native UI interaction/visual, new listening and physical7.1.4 pending'])
(repo / 'research/drive_aux_v1_summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(dict(result='pass', tests=37, c_files=len(rows), recording_schema=2,
                      device_hash=device['record_hash'], review=str(published)), ensure_ascii=False))

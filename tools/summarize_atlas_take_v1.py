"""Verify saved native takes and bind source/binary/evidence hashes for handoff."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',required=True,type=Path)
args=parser.parse_args()
repo=Path(__file__).resolve().parents[1]
root=args.workspace/'references/analysis/atlas_take_v1'
final=root/'final'
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf

def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def fnv(data):
    h=14695981039346656037
    for byte in data:h=((h^byte)*1099511628211)&((1<<64)-1)
    return f'{h:016x}'

device=json.loads((final/'设备 行程.vslrun.json').read_text(encoding='utf-8'))
assert device['verified'] and device['rejected_block_excluded']
assert device['frames']==144123 and device['record_hash']==device['play_hash']
for prefix in ('record','play'):
    assert device[prefix+'_queue_empty']==device[prefix+'_over_budget']==0
    assert abs(device[prefix+'_device_seconds']-device['frames']/48000)<.06
    assert abs(device[prefix+'_wall_seconds']-device['frames']/48000)<.15

# Empty working directory proves the export does not consult voices/ paths.
isolated=final/'without-models';isolated.mkdir(exist_ok=True)
exports=[]
for channels in (2,12):
    command=[str(repo/'handoff-build/bin/Release/VslAtlasTake_render.exe'),str(final/'设备 行程.vslrun'),
             str(final/f'export_{channels}.wav'),'--channels',str(channels)]
    result=subprocess.run(command,cwd=isolated,capture_output=True,text=True,check=True)
    record=json.loads(result.stdout);assert record['verified'] and record['frames']==device['frames']
    audio,rate=sf.read(final/f'export_{channels}.wav',dtype='float32',always_2d=True)
    assert rate==48000 and audio.shape==(device['frames'],channels) and np.isfinite(audio).all()
    assert record['audio_hash']==fnv(np.asarray(audio,dtype='<f4').tobytes())
    if channels==2:assert record['audio_hash']==device['record_hash']
    exports.append(dict(command=command,returncode=result.returncode,**record))
assert exports[0]['source_hash']==exports[1]['source_hash']
(final/'exports.json').write_text(json.dumps(exports,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')

log=final/'LastTest.log'
assert log.read_bytes().count(b'Test Passed.')==35 and b'Test Failed.' not in log.read_bytes()
focused=final/'LastTest-focused.log'
assert focused.read_bytes().count(b'Test Passed.')==1 and b'Test Failed.' not in focused.read_bytes()
for name in ('atlas_take_build_attempt2.log','atlas_take_build_attempt3.log','atlas_take_ui_build_final.log','atlas_take_build_final.log'):
    shutil.copy2(Path('E:/VSL QA 20261112')/name,root/name)

with (repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
for row in rows:assert row['SHA-256']==sha(repo/row['文件']),row['文件']
code=[p for folder in ('modules/atlas_take','modules/atlas_take_io','modules/win_output','experiments/atlas_take_v1','experiments/atlas_monitor_v1')
      for p in (repo/folder).iterdir() if p.is_file()]
report=dict(schema='vsl.atlas-take-summary/1',date='2026-11-12',result='pass',tests=35,
    ui_interaction_verified=False,ui_visual_verified=False,human_timbre_accepted=False,
    base_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
    render_id=device['render_id'],device=device,exports=exports,evidence_root=str(root),
    c_index_sha256=sha(repo/'handoff/C文件索引.csv'),source_sha256={p.relative_to(repo).as_posix():sha(p) for p in code},
    evidence_sha256={p.relative_to(root).as_posix():sha(p) for p in sorted(root.rglob('*')) if p.is_file()},
    binary_sha256={name:sha(repo/'handoff-build/bin/Release'/name) for name in
        ('VslAtlasMonitor.exe','VslAtlasTake_render.exe','VslAtlasTake_device_checks.exe')},
    unchanged_model_sha256={p.relative_to(repo).as_posix():sha(p) for folder in ('dna_bank_v1','coherent_low_v1')
        for p in (repo/'voices'/folder).glob('*.model')},
    limits=['New UI interaction/visual checks pending: Computer Use node_repl absent',
            'Short muted native test, not long-run/hard realtime/speaker acceptance',
            'Fresh frame0 only; strict renderer/build identity; no arbitrary DSP snapshot',
            'A4/E2 and driving LF/residual listening remain pending'])
(repo/'research/atlas_take_v1_summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(result='pass',tests=35,render_id=report['render_id'],device_frames=device['frames'],ui_verified=False)))

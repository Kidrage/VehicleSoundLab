"""Seal final residual-atlas source, offline, device and UI evidence hashes."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil
import sys

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True)
args=parser.parse_args()
repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
root=args.workspace/'references/analysis/residual_atlas_v1'
def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
offline=read(root/'controls_final/verification.json');ui=read(root/'ui_final/verification.json')
assert offline['result']==ui['result']=='pass' and ui['muted'] and ui['residual_control']
bin_dir=repo/'handoff-build/bin/Release'
assert offline['probe_sha256']==sha(bin_dir/'VslAtlasDrive_probe.exe')
assert offline['fit_sha256']==sha(root/'fitted/report.json')
assert offline['models_index_sha256']==sha(repo/'voices/residual_atlas_v1/index.json')
assert ui['binary_sha256']==sha(bin_dir/'VslAtlasMonitor.exe')
assert ui['verifier_sha256']==sha(repo/'tools/verify_atlas_ui_v1.py')
assert offline['commands_sha256']==sha(root/'controls_final/commands.json')
for command in read(root/'controls_final/commands.json'):
    for filename,expected in command['files_sha256'].items():assert sha(root/'controls_final'/filename)==expected
devices=[]
for name in ('bench','pedals','stopped','cabin_restart'):
    path=root/'device_final'/(name+'.json');r=read(path)
    assert r['healthy'] and r['offline_float_equal'] and r['queue_empty']==r['budget_exceeded']==0
    x,rate=sf.read(path.with_suffix('.wav'),always_2d=True)
    assert rate==48000 and x.shape==(r['frames'],2) and np.isfinite(x).all()
    assert abs(abs(x).max()-r['peak'])<1e-8 and abs(x).max()<.95
    if name in ('bench','pedals','cabin_restart'):assert any(c['residual_gain']>0 for c in r['controls'])
    devices.append(dict(name=name,**{k:v for k,v in r.items() if k not in ('schema','controls')},controls=len(r['controls'])))
test=repo/'handoff-build/Testing/Temporary/LastTest.log'
text=test.read_text(encoding='utf-8',errors='replace')
assert text.count('Test Passed.')==33 and 'Test Failed.' not in text
saved=root/'ctest.log'
if saved.exists():assert sha(saved)==sha(test)
else:shutil.copy2(test,saved)
with (repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig',newline='') as stream:rows=list(csv.DictReader(stream))
for row in rows:assert sha(repo/row['文件'])==row['SHA-256']
code=[p for directory in ('modules/residual_atlas','modules/sound_residual','modules/atlas_drive',
    'experiments/residual_atlas_v1','experiments/atlas_monitor_v1','voices/residual_atlas_v1')
    for p in (repo/directory).iterdir() if p.is_file()]
code += [repo/'tools'/name for name in ('fit_residual_atlas_v1.py','verify_residual_atlas_v1.py',
    'verify_atlas_ui_v1.py','summarize_residual_atlas_v1.py','freeze_residual_atlas_v1.py')]
code += [repo/'experiments/atlas_drive_v1/probe.c',repo/'handoff/CMakeLists.txt']
inputs=['fitted/report.json','controls_final/verification.json','controls_final/commands.json',
        'build-and-tests.log','build-and-tests-final.log','build-host-final.log','ctest.log']
for directory in ('device_final','ui_final'):
    inputs += [p.relative_to(root).as_posix() for p in (root/directory).iterdir() if p.is_file()]
summary=dict(schema='vsl.residual-atlas-summary/1',result='pass',human_accepted=False,
    tests=33,source_recordings=2,acoustic_contexts=2,anchors=6,oscillators=512,default_amount=0,
    offline=offline,device=devices,ui=ui,c_index_rows=len(rows),c_index_sha256=sha(repo/'handoff/C文件索引.csv'),
    evidence_root=str(root),evidence_sha256={name:sha(root/name) for name in inputs},
    source_sha256={p.relative_to(repo).as_posix():sha(p) for p in code},
    binaries_sha256={name:sha(bin_dir/name) for name in ('VslAtlasDrive_probe.exe','VslAtlasMonitor.exe',
                        'VslAtlasMonitor_device_verify.exe','VslSystem.exe')},
    limits=['Experimental fixed-Hz spectral interpolation; no measured load/state colour axis or complete engine atlas',
        'Independent LF/intake/mechanics physical voices and new take format remain incomplete',
        'Only short muted stereo device checks; offline5ms overruns exist; no long-run/hard-realtime guarantee',
        '12channel source parity is not actual7.1.4 speaker or spatial listening acceptance',
        'Coarse2048-point fit-window boundary leakage is preserved separately from high-resolution source validation'])
(repo/'research/residual_atlas_v1_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(result='pass',tests=33,anchors=6,device_cases=len(devices),index_rows=len(rows)),ensure_ascii=False))

"""Bind final native device/UI evidence, frozen parity and the C ownership index."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True)
args=parser.parse_args()
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
repository=Path(__file__).resolve().parents[1]
root=args.workspace/'references/analysis/atlas_realtime_v1'
def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def read(path):return json.loads(path.read_text(encoding='utf-8'))
cache=read(root/'cache/verification.json');ui=read(root/'ui_final/verification.json')
assert cache['result']==ui['result']=='pass'
assert cache['source_sha256']==sha(repository/'modules/sound_dna/texture.c')
assert cache['binary_sha256']==sha(repository/'handoff-build/bin/Release/VslSoundDna_probe.exe')
assert cache['verifier_sha256']==sha(repository/'tools/verify_texture_cache_v1.py')
assert ui['binary_sha256']==sha(repository/'handoff-build/bin/Release/VslAtlasMonitor.exe')
assert ui['verifier_sha256']==sha(repository/'tools/verify_atlas_ui_v1.py')
command=read(root/'device_final/command.json')
assert command['returncode']==0
assert command['binary_sha256']==sha(repository/'handoff-build/bin/Release/VslAtlasMonitor_device_verify.exe')
for name,expected in command['files_sha256'].items():assert sha(root/'device_final'/name)==expected
device=[]
for name in ('bench','pedals','stopped','cabin_restart'):
    record=read(root/'device_final'/(name+'.json'))
    audio,rate=sf.read(root/'device_final'/(name+'.wav'),always_2d=True)
    assert record['healthy'] and record['offline_float_equal'] and record['queue_empty']==record['budget_exceeded']==0
    assert rate==48000 and audio.shape==(record['frames'],2) and np.isfinite(audio).all()
    assert abs(abs(audio).max()-record['peak'])<1e-8 and abs(audio).max()<.95
    device.append(dict(name=name,**{k:v for k,v in record.items() if k not in ('controls','schema')},
        adopted_controls=len(record['controls']),wav_sha256=sha(root/'device_final'/(name+'.wav'))))
test_log=repository/'handoff-build/Testing/Temporary/LastTest.log'
log=test_log.read_bytes().decode('utf-8',errors='replace')
assert log.count('Test Passed.')==30 and 'Test Failed.' not in log
with (repository/'handoff/C文件索引.csv').open(encoding='utf-8-sig',newline='') as stream:
    rows=list(csv.DictReader(stream))
for row in rows:assert sha(repository/row['文件'])==row['SHA-256'],row['文件']
launcher=repository/'handoff-build/bin/Release/VslSystem.exe'
subprocess.run([str(launcher),'--rebuilt','--check'],cwd=repository,check=True,timeout=10)
inputs=['cache/verification.json','device_final/command.json','ui_final/verification.json','build_final.log']
for directory in ('device_final','ui_final'):
    inputs.extend(p.relative_to(root).as_posix() for p in (root/directory).iterdir() if p.is_file())
code=[p for folder in ('modules/atlas_monitor','modules/win_output','modules/sound_dna','experiments/atlas_monitor_v1')
    for p in (repository/folder).iterdir() if p.is_file() and p.suffix in ('.c','.h','.txt')]
report=dict(schema='vsl.atlas-realtime/1',result='pass',human_accepted=False,
    cache=cache,device=device,ui=ui,test_count=30,test_log_sha256=sha(test_log),
    c_index_rows=len(rows),c_index_sha256=sha(repository/'handoff/C文件索引.csv'),launcher_paths_pass=True,
    evidence_root=str(root),evidence_sha256={p:sha(root/p) for p in inputs},
    source_sha256={p.relative_to(repository).as_posix():sha(p) for p in code},
    binaries_sha256={name:sha(repository/'handoff-build/bin/Release'/name) for name in
        ('VslAtlasMonitor.exe','VslAtlasMonitor_device_verify.exe','VslAtlasDrive_probe.exe','VslSoundDna_probe.exe','VslSystem.exe')},
    limits=['Short muted stereo device test; no long-run or physical loudspeaker acceptance',
        'A4/E2 timbres unaccepted; sparse state/load coverage; A root/RPM hypothesis',
        'Only DNA and optional legacy events; independent LF/intake/noise absent',
        'Bounded debug controls are not a production take/replay format'])
(repository/'research/atlas_realtime_v1_summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(result='pass',tests=30,indexed_c_files=len(rows),device_cases=len(device))))

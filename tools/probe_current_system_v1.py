"""Fresh muted native-device/control/take checks of the current built system."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--out',type=Path,required=True)
args=parser.parse_args();repo=Path(__file__).resolve().parents[1]
args.out.mkdir(parents=True,exist_ok=False);(args.out/'bin').mkdir();(args.out/'device').mkdir()
shutil.copy2(Path(__file__),args.out/Path(__file__).name)
index=repo/'handoff/C文件索引.csv';shutil.copy2(index,args.out/index.name)
with index.open(encoding='utf-8-sig',newline='') as stream:code=list(csv.DictReader(stream))
assert len(code)==442
for row in code:assert sha(repo/row['文件'])==row['SHA-256'],row['文件']
names=['VslAtlasMonitor_device_verify.exe','VslAtlasTake_device_checks.exe','VslAtlasTake_render.exe','VslAtlasMonitor.exe']
for name in names:shutil.copy2(repo/'handoff-build/bin/Release'/name,args.out/'bin'/name)
r=dict(schema='vsl.current-system-device/1',result='running',commands=[],c_h_count=442,c_index_sha256=sha(index),
    source_sha256={Path(__file__).relative_to(repo).as_posix():sha(Path(__file__))},
    binary_sha256={name:sha(args.out/'bin'/name) for name in names},
    base_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),muted=True)
(args.out/'metadata.json').write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8',newline='\n')
try:
    commands=[[str(args.out/'bin/VslAtlasMonitor_device_verify.exe'),str(args.out/'device')],
        [str(args.out/'bin/VslAtlasTake_device_checks.exe'),str(args.out/'device_take.vslrun')]]
    commands += [[str(args.out/'bin/VslAtlasTake_render.exe'),str(args.out/'device_take.vslrun'),str(args.out/f'take_{c}.wav'),'--channels',str(c)] for c in (2,12)]
    for i,command in enumerate(commands):
        result=subprocess.run(command,cwd=repo,capture_output=True,text=True,timeout=90)
        r['commands'].append(dict(command=command,exit_code=result.returncode,stdout=result.stdout,stderr=result.stderr))
        (args.out/f'command_{i}.log').write_text(result.stdout+result.stderr,encoding='utf-8',newline='\n')
        print(json.dumps(dict(command=i,exit_code=result.returncode,stdout=result.stdout)),flush=True)
        result.check_returncode()
    r['device_cases']={name:json.loads((args.out/'device'/(name+'.json')).read_text(encoding='utf-8')) for name in ('bench','pedals','stopped','cabin_restart')}
    for case in r['device_cases'].values():assert case['healthy'] and case['offline_float_equal'] and case['queue_empty']==0
    r['take']=json.loads((args.out/'device_take.vslrun.json').read_text(encoding='utf-8'));assert r['take']['verified']
    exports=[json.loads(x['stdout']) for x in r['commands'][2:]]
    assert all(x['verified'] for x in exports) and exports[0]['source_hash']==exports[1]['source_hash']
    r.update(result='short_device_checks_passed',exports=exports,
        hardware_12channel_verified=False,long_run_verified=False,human_timbre_accepted=False,
        meaning='Actual muted stereo queues, adopted-control replay, ignition/pedals/shifts/release/off, transport/model switch and self-contained take/save/replay/cancel;12channels only offline. UI interaction is not newly tested.')
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:(args.out/'report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')

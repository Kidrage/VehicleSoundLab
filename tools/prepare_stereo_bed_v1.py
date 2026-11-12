"""Preserve the currently deployed renderer before adding optional stereo-bed routing."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',required=True,type=Path)
args=parser.parse_args();repo=Path(__file__).resolve().parents[1]
out=args.workspace/'references/analysis/stereo_bed_v1/before';out.mkdir(parents=True,exist_ok=False)
(out/'bin').mkdir();(out/'renders').mkdir()
shutil.copy2(__file__,out/Path(__file__).name)
index=repo/'handoff/C文件索引.csv';shutil.copy2(index,out/index.name)
with index.open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
assert len(rows)==445
for row in rows:assert sha(repo/row['文件'])==row['SHA-256']
names=['VslAtlasDrive_probe','VslAtlasMonitor','VslAtlasMonitor_device_verify','VslAtlasTake_render','VslAtlasTake_device_checks']
for name in names:shutil.copy2(repo/'handoff-build/bin/Release'/(name+'.exe'),out/'bin'/(name+'.exe'))
revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
subprocess.run(['git','archive','--format=zip','--output='+str(out/'source.zip'),revision],cwd=repo,check=True)
a=[str(repo/'voices/exterior_anchors_v1'/f'A Stationary {name}.model') for name in ['Low','Lower Mid','Upper Mid','High']]
e=[str(repo/'voices/cabin_anchors_v1'/f'E Cabin {name}.model') for name in ['Lower','Upper']]
cases=[('A_direct',a,2,0),('A_objects12',a,12,1),('E_objects2',e,2,1)]
report=dict(schema='vsl.stereo-bed-before/1',commit=revision,C_H_count=len(rows),cases=[],binaries={p.name:sha(p) for p in (out/'bin').iterdir()})
for name,models,channels,spatial in cases:
    options=['--seconds','4','--scenario','shifts','--channels',str(channels),'--spatial',str(spatial),
             '--body-mix','.6','--residual-gain','.35','--events','.2','--room','.2',
             '--intake','.2','--mechanical','.2','--air','.2','--road','.2','--wind','.2']
    for model in models[2:]:options+=['--anchor',model]
    for model in models:options+=['--residual-anchor',str(repo/'voices/residual_atlas_v1'/(Path(model).stem+'.residual'))]
    command=[str(out/'bin/VslAtlasDrive_probe.exe'),*models[:2],str(out/'renders'/name),*options]
    result=subprocess.run(command,cwd=repo,capture_output=True,timeout=60)
    (out/(name+'.log')).write_bytes(result.stdout+result.stderr);assert result.returncode==0
    report['cases'].append(dict(name=name,models=models,options=options,frames=192000))
report['files']={p.relative_to(out).as_posix():sha(p) for p in sorted(out.rglob('*')) if p.is_file()}
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(out=str(out),cases=len(cases),files=len(report['files']))))

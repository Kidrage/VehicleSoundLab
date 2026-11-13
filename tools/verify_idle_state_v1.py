"""Build pre-spatial idle study in a separate tree and preserve every attempt."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time
import xml.etree.ElementTree as ET

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--out',type=Path,required=True)
p.add_argument('--phase',choices=['kernel','all'],required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];build=repo/'build-idle-state-v1'

def sha(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def load(path):return json.loads(path.read_text(encoding='utf-8'))
def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
a.out.mkdir(parents=True,exist_ok=False)
r=dict(result='running',phase=a.phase,sources={},commands=[],runtime_default_changed=False)
def command(label,argv):
    started=time.perf_counter();done=subprocess.run(list(map(str,argv)),cwd=repo,capture_output=True,timeout=600)
    path=a.out/(label+'.log');path.write_bytes(done.stdout+done.stderr)
    row=dict(label=label,argv=list(map(str,argv)),exit=done.returncode,seconds=time.perf_counter()-started,log_sha256=sha(path))
    r['commands'].append(row);save(a.out/'report.json',r);print(json.dumps(row),flush=True)
    if done.returncode:raise RuntimeError(label+' failed: '+str(path))
try:
    paths={Path(__file__),repo/'research/idle_state_v1_plan.json',repo/'Build-Idle-State-Study.ps1'}
    for folder in ['src','modules','experiments']:
        paths.update(x for x in (repo/folder).rglob('*') if x.is_file() and (x.suffix.lower() in ('.c','.h') or x.name=='CMakeLists.txt'))
    paths.update([repo/'CMakeLists.txt',repo/'handoff/CMakeLists.txt',repo/'modules/atlas_take/atlas_take_build.h.in'])
    for path in sorted(paths):
        target=a.out/'exact_sources'/path.relative_to(repo);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
        r['sources'][path.relative_to(repo).as_posix()]=sha(path)
    old=a.workspace/'baselines/accel_material_v1'
    c=load(old/'C_files_sha256.json');voices=load(old/'voice_files_sha256.json')
    r['modified_original_C_H']=[name for name,digest in c.items() if sha(repo/name)!=digest]
    assert set(r['modified_original_C_H'])=={'modules/atlas_drive/render.h','modules/atlas_drive/render.c','modules/atlas_take/assets.c'},r['modified_original_C_H']
    assert all(sha(repo/name)==digest for name,digest in voices.items())
    command('configure',['cmake','-S',repo/'experiments/idle_state_v1','-B',build,'-G','Visual Studio 17 2022','-A','x64'])
    target=['--target','idle_layer_checks','idle_state_checks','idle_state_probe'] if a.phase=='kernel' else []
    command('build',['cmake','--build',build,'--config','Release','--parallel','2',*target])
    select=['-R','^(independent_modal_layer_contract|idle_state_source_integration)$'] if a.phase=='kernel' else []
    command('ctest',['ctest','--test-dir',build,'-C','Release','--output-on-failure','--output-junit',a.out/'ctest.xml',*select])
    tests=ET.parse(a.out/'ctest.xml').getroot();cases=tests.findall('.//testcase')
    assert not tests.findall('.//failure') and not tests.findall('.//error')
    assert len(cases)==(2 if a.phase=='kernel' else 57),len(cases)
    shutil.copy2(build/'CMakeCache.txt',a.out/'CMakeCache.txt')
    r.update(result='passed',tests=len(cases),voices_unchanged=len(voices),cache_sha256=sha(build/'CMakeCache.txt'))
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)

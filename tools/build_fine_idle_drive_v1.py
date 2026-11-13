"""Capture exact executed sources and build the typed idle driving branch."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time
import xml.etree.ElementTree as ET

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--out',type=Path,required=True)
p.add_argument('--phase',choices=['kernel','all','fixtures'],required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];build=repo/'build-fine-idle-drive-v1'
a.out.mkdir(parents=True,exist_ok=False)


def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def save():
    (a.out/'report.json').write_text(json.dumps(r,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')


r=dict(result='running',phase=a.phase,sources={},commands=[],default_binary_replaced=False)
try:
    names=subprocess.check_output(['git','ls-files','-z'],cwd=repo).decode('utf-8').split('\0')
    names+=subprocess.check_output(['git','ls-files','--others','--exclude-standard','-z'],cwd=repo).decode('utf-8').split('\0')
    names=set(name for name in names if name and (Path(name).suffix.lower() in ('.c','.h','.in') or name.endswith('CMakeLists.txt')))
    names.update(['tools/build_fine_idle_drive_v1.py','research/fine_idle_drive_v1_plan.json','Build-Fine-Idle-Drive-Study.ps1','Launch-Fine-Idle-Drive-Study.cmd'])
    for name in sorted(names):
        source=repo/name;dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,dest);r['sources'][name]=sha(source)
    commands=[['cmake','-S',repo/'experiments/fine_idle_drive_v1','-B',build,'-G','Visual Studio 17 2022','-A','x64'],
              ['cmake','--build',build,'--config','Release','--parallel','2']]
    if a.phase=='kernel':commands[-1]+=['--target','fine_idle_layer_checks','fine_idle_owned_checks']
    if a.phase=='fixtures':commands[-1]+=['--target','VslAtlasTake_checks','VslFullRecipeDrive_checks']
    commands+=[['ctest','--test-dir',build,'-C','Release','--output-on-failure','--output-junit',a.out/'ctest.xml']]
    if a.phase=='kernel':commands[-1]+=['-R','^fine_idle_(layer_contract|owned_driving_take)$']
    if a.phase=='fixtures':commands[-1]+=['-R','^handoff_(atlas_take_contract|full_recipe_driving_contract)$']
    for command in commands:
        started=time.perf_counter();argv=list(map(str,command))
        done=subprocess.run(argv,cwd=repo,capture_output=True,timeout=600)
        log=a.out/('command_%02d.log'%len(r['commands']));log.write_bytes(done.stdout+done.stderr)
        row=dict(argv=argv,exit_code=done.returncode,seconds=time.perf_counter()-started,log=log.name,sha256=sha(log))
        r['commands'].append(row);save();print(json.dumps(row),flush=True)
        if done.returncode:raise RuntimeError(str(log))
    xml=ET.parse(a.out/'ctest.xml').getroot();tests=xml.findall('.//testcase')
    assert not xml.findall('.//failure') and not xml.findall('.//error')
    assert len(tests)==(61 if a.phase=='all' else 2),len(tests)
    shutil.copy2(build/'CMakeCache.txt',a.out/'CMakeCache.txt')
    r.update(result='passed',tests=len(tests),cache_sha256=sha(build/'CMakeCache.txt'))
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save()

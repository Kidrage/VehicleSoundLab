"""Build the optional observation-bed system without replacing running binaries."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
args=p.parse_args();repo=Path(__file__).resolve().parents[1];args.out.mkdir(parents=True,exist_ok=False)
r=dict(result='running',commands=[],source_sha256={})
paths=[Path(__file__),repo/'CMakeLists.txt',repo/'handoff/CMakeLists.txt']
for folder in ['src','modules','experiments']:
    paths.extend(x for x in (repo/folder).rglob('*') if x.is_file() and (x.suffix in ('.c','.h','.in') or x.name=='CMakeLists.txt'))
for path in paths:
    target=args.out/'exact_sources'/path.relative_to(repo);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
    r['source_sha256'][path.relative_to(repo).as_posix()]=sha(path)
build=repo/'build-stereo-bed-v1'
try:
    for command in [['cmake','-S',str(repo/'handoff'),'-B',str(build),'-A','x64'],
                    ['cmake','--build',str(build),'--config','Release','--parallel','4'],
                    ['ctest','--test-dir',str(build),'-C','Release','--parallel','4','--output-on-failure']]:
        result=subprocess.run(command,cwd=repo,capture_output=True,timeout=600)
        name=f'command_{len(r["commands"])}.log';(args.out/name).write_bytes(result.stdout+result.stderr)
        r['commands'].append(dict(argv=command,exit_code=result.returncode,log=name,sha256=sha(args.out/name)))
        print(json.dumps(dict(command=command[0],exit_code=result.returncode,log=name)),flush=True)
        assert result.returncode==0,name
    r.update(result='build_and_41tests_pass',build=str(build),
             binaries={str(x.relative_to(build)):sha(x) for x in build.rglob('*.exe') if 'CompilerId' not in str(x)})
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:(args.out/'report.json').write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8',newline='\n')

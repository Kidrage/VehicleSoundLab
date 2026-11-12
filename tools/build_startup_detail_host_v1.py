"""Build optional native startup detail recipe; verify the existing schema identity."""
import argparse,hashlib,json,shutil,subprocess
from pathlib import Path
def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];a.out.mkdir(parents=True,exist_ok=False)
r=dict(result='running',commands=[],source_sha256={})
try:
    paths=[Path(__file__),repo/'CMakeLists.txt',repo/'handoff/CMakeLists.txt']
    for folder in ('src','modules','experiments','tests'):
        paths.extend(x for x in (repo/folder).rglob('*') if x.is_file() and (x.suffix in ('.c','.h','.in') or x.name=='CMakeLists.txt'))
    for path in paths:
        name=path.relative_to(repo).as_posix();dest=a.out/'exact_sources'/name
        dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,dest);r['source_sha256'][name]=sha(path)
    build=repo/'build-startup-detail-host-v1'
    for cmd in (['cmake','-S',repo/'handoff','-B',build,'-A','x64'],
                ['cmake','--build',build,'--config','Release','--parallel','4'],
                ['ctest','--test-dir',build,'-C','Release','--parallel','4','--output-on-failure']):
        cmd=list(map(str,cmd));print(json.dumps(dict(running=cmd[:5])),flush=True)
        done=subprocess.run(cmd,cwd=repo,capture_output=True,timeout=600)
        log=a.out/f'command_{len(r["commands"]):02}.log';log.write_bytes(done.stdout+done.stderr)
        r['commands'].append(dict(argv=cmd,exit_code=done.returncode,log=log.name,sha256=sha(log)))
        assert done.returncode==0,log.name
    text=(a.out/'command_02.log').read_text(encoding='utf-8')
    assert '100% tests passed' in text and 'out of 46' in text
    r.update(result='build_and_46tests_pass',build=str(build),binaries={str(x.relative_to(build)):sha(x) for x in build.rglob('*.exe') if 'CompilerId' not in str(x)})
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:(a.out/'report.json').write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(result=r['result'],build=r.get('build'))))

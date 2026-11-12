"""Author the two-endpoint candidate, freeze sources, build and test the unified host."""
import argparse,json,shutil,subprocess,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(a.workspace/'tools/python_deps'))
from drive_evidence_v1.sources import sha
a.out.mkdir(parents=True,exist_ok=False)
r=dict(result='running',commands=[],source_sha256={})
try:
    before=a.workspace/'references/analysis/startup_drive_v1/before/report.json'
    data=json.loads(before.read_text(encoding='utf-8'));assert data['result']=='before_and_motion_observations_frozen'
    target=repo/'voices/startup_drive_v1/A cabin motion.start';target.parent.mkdir(exist_ok=True)
    halves=data['half_moments'];lines=['VSL_START_TEXTURE 2 0.005 0.035','48000 16 32']
    import math
    for first,last in zip(*halves):
        values=list(first['hz'])
        for row in (first,last):
            l,rp=row['power'];re,im=row['cross'];den=math.sqrt(l*rp)
            assert den>0 and math.hypot(re,im)<=den+1e-12
            values.extend([l,rp,re/den,im/den])
        lines.append(' '.join(format(v,'.17g') for v in values))
    authored=('\n'.join(lines)+'\n').encode('ascii')
    if target.exists():assert target.read_bytes()==authored
    else:target.write_bytes(authored)
    r['model_sha256']=sha(target);shutil.copy2(target,a.out/'A cabin motion.start')
    paths=[Path(__file__),repo/'CMakeLists.txt',repo/'handoff/CMakeLists.txt']
    for folder in ['src','modules','experiments','tests']:
        paths.extend(x for x in (repo/folder).rglob('*') if x.is_file() and (x.suffix in ('.c','.h','.in') or x.name=='CMakeLists.txt'))
    for path in paths:
        dest=a.out/'exact_sources'/path.relative_to(repo);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,dest)
        r['source_sha256'][path.relative_to(repo).as_posix()]=sha(path)
    build=repo/'build-startup-drive-v1'
    for cmd in [['cmake','-S',repo/'handoff','-B',build,'-A','x64'],
                ['cmake','--build',build,'--config','Release','--parallel','4'],
                ['ctest','--test-dir',build,'-C','Release','--parallel','4','--output-on-failure']]:
        cmd=list(map(str,cmd));print(json.dumps({'running':cmd[:4]}),flush=True)
        done=subprocess.run(cmd,cwd=repo,capture_output=True,timeout=600)
        name=f'command_{len(r["commands"]):02}.log';(a.out/name).write_bytes(done.stdout+done.stderr)
        r['commands'].append(dict(argv=cmd,exit_code=done.returncode,log=name,sha256=sha(a.out/name)))
        assert done.returncode==0,name
    r.update(result='build_and_43tests_pass',build=str(build),binaries={str(x.relative_to(build)):sha(x) for x in build.rglob('*.exe') if 'CompilerId' not in str(x)})
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:(a.out/'report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(result=r['result'],build=r.get('build'))))

"""Build only the modular offline capture adapter; retain exact inputs/logs."""
import argparse
from pathlib import Path
import shutil
import subprocess
from research_archive_v1 import load,save,sha

p=argparse.ArgumentParser(description=__doc__)
for name in ('workspace','out'):p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
a.out.mkdir(parents=True,exist_ok=False)
r=dict(result='running',sources={},commands=[])
try:
    prior=a.workspace/'baselines/catalog_local_F3_v1/evidence'
    for file in ['C_files_sha256.json','voice_files_sha256.json']:
        rows=load(prior/file)
        assert all(sha(repo/n)==h for n,h in rows.items())
        shutil.copy2(prior/file,a.out/('prior_'+file))
    names=set()
    for flags in [['ls-files','-z'],['ls-files','--others','--exclude-standard','-z']]:
        names.update(subprocess.check_output(['git']+flags,cwd=repo).decode('utf8').split('\0'))
    names.discard('')
    names={n for n in names if Path(n).suffix in ('.c','.h','.cmake','.in') or n.endswith('CMakeLists.txt')}
    names.update(['tools/build_joint_capture_v1.py','research/F3_driver_joint_v1_plan.json'])
    for name in sorted(names):
        dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,dest)
        r['sources'][name]=sha(dest)
    build=repo/'build-joint-capture-v1'
    commands=[['cmake','-S',repo/'experiments/joint_capture_v1','-B',build,'-G','Visual Studio 17 2022','-A','x64'],
              ['cmake','--build',build,'--config','Release','--parallel','2','--target','joint_capture']]
    for i,argv in enumerate(commands):
        argv=list(map(str,argv));print('RUN',argv[:4],flush=True)
        done=subprocess.run(argv,cwd=repo,capture_output=True,timeout=900)
        log=a.out/f'command{i}.log';log.write_bytes(done.stdout+done.stderr)
        r['commands'].append(dict(argv=argv,exit_code=done.returncode,log=log.name,sha256=sha(log)));save(a.out/'report.json',r)
        assert done.returncode==0,log
    binary=build/'bin/Release/joint_capture.exe';shutil.copy2(binary,a.out/'joint_capture.exe')
    r.update(result='joint_capture_built',binary_sha256=sha(binary),prior_C_H_exact=667,prior_voices_exact=82,shared_C_changed=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(r['result'])

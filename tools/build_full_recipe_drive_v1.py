"""Capture exact C/CMake sources and run the requested concrete build stage."""
import argparse,hashlib,json,shutil,subprocess
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--out',type=Path,required=True);p.add_argument('--stage',choices=['kernel','all'],required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];build=repo/'build-full-recipe-drive-v1'
a.out.mkdir(parents=True,exist_ok=False)
sha=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest()
r=dict(schema='vsl.full-recipe-build/1',result='running',stage=a.stage,sources={},commands=[])
try:
    tracked=subprocess.check_output(['git','ls-files'],cwd=repo,text=True).splitlines()
    untracked=subprocess.check_output(['git','ls-files','--others','--exclude-standard'],cwd=repo,text=True).splitlines()
    for name in sorted(set(tracked+untracked)):
        if Path(name).suffix.lower() in ('.c','.h','.in') or name.endswith('CMakeLists.txt'):
            path=repo/name;target=a.out/'exact_sources'/name;target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(path,target);r['sources'][name]=sha(path)
    shutil.copy2(__file__,a.out/'executed_build.py')
    commands=[['cmake','-S',str(repo/'handoff'),'-B',str(build),'-G','Visual Studio 17 2022','-A','x64'],
              ['cmake','--build',str(build),'--config','Release','--parallel']]
    if a.stage=='kernel':commands[1]+=['--target','VslFullRecipeKernel_checks']
    commands+=[['ctest','--test-dir',str(build),'-C','Release','--output-on-failure']]
    if a.stage=='kernel':commands[-1]+=['-R','^handoff_full_recipe_kernel_contract$']
    for command in commands:
        done=subprocess.run(command,cwd=repo,capture_output=True,timeout=600)
        log=a.out/f'command_{len(r["commands"]):02}.log';log.write_bytes(done.stdout+done.stderr)
        r['commands'].append(dict(argv=command,exit_code=done.returncode,log=log.name,sha256=sha(log)))
        print(json.dumps(dict(command=command[:2],exit_code=done.returncode,log=str(log))),flush=True)
        assert done.returncode==0,(command,log)
    r.update(result='passed',cache_sha256=sha(build/'CMakeCache.txt'))
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:(a.out/'report.json').write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8')

"""Capture stable executed sources and build/test the unified voice catalog."""
import argparse,shutil,subprocess,time
from pathlib import Path
from research_archive_v1 import save,sha
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True)
p.add_argument('--phase',choices=['focused','all','host'],required=True);a=p.parse_args()
repo=Path(__file__).resolve().parents[1];build=repo/'build-catalog-drive-v1';a.out.mkdir(parents=True,exist_ok=False)
r=dict(result='running',phase=a.phase,sources={},commands=[])
try:
    names=subprocess.check_output(['git','ls-files','-z'],cwd=repo).decode('utf-8').split('\0')
    names+=subprocess.check_output(['git','ls-files','--others','--exclude-standard','-z'],cwd=repo).decode('utf-8').split('\0')
    for n in sorted(set(n for n in names if n and (Path(n).suffix in ('.c','.h','.cmake','.in') or n.endswith('CMakeLists.txt')))):
        dest=a.out/'exact_sources'/n;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/n,dest);r['sources'][n]=sha(repo/n)
    shutil.copy2(__file__,a.out/'build_catalog_drive_v1.py')
    commands=[['cmake','-S',repo/'experiments/catalog_drive_v1','-B',build,'-G','Visual Studio 17 2022','-A','x64'],
        ['cmake','--build',build,'--config','Release','--parallel','2']]
    if a.phase=='focused':commands[-1]+=['--target','catalog_contract_checks','catalog_render_checks','VslAtlasMonitor']
    if a.phase=='host':
        commands[-1]+=['--target','VslAtlasMonitor']
        commands+=[[build/'bin/Release/VslAtlasMonitor.exe','--catalog','--muted','--ui-check',a.out/'ui.json']]
    else:
        commands+=[['ctest','--test-dir',build,'-C','Release','--output-on-failure','--output-junit',a.out/'ctest.xml']]
        if a.phase=='focused':commands[-1]+=['-R','^catalog_']
    for command in commands:
        argv=list(map(str,command));start=time.perf_counter();done=subprocess.run(argv,cwd=repo,capture_output=True,timeout=600)
        log=a.out/('command_%02d.log'%len(r['commands']));log.write_bytes(done.stdout+done.stderr)
        row=dict(argv=argv,exit_code=done.returncode,seconds=time.perf_counter()-start,log=log.name,sha256=sha(log));r['commands'].append(row)
        save(a.out/'report.json',r);print(row,flush=True)
        if done.returncode:raise RuntimeError(str(log))
    shutil.copy2(build/'CMakeCache.txt',a.out/'CMakeCache.txt');r['result']='passed'
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)

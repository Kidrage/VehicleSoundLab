"""Preserve executed inputs and logs while building the layer-listening host."""
import argparse,shutil,subprocess,time
from pathlib import Path
from research_archive_v1 import sha,save

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--out',type=Path,required=True)
p.add_argument('--phase',choices=['old','focused','all'],required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
a.out.mkdir(parents=True,exist_ok=False)
before=Path('E:/VehicleSoundLab/references/analysis/layer_monitor_v1/before/source')
build=repo/('build-layer-monitor-old-v1' if a.phase=='old' else 'build-layer-monitor-v1')
r=dict(result='running',phase=a.phase,commands=[],sources={})
try:
    if a.phase=='old':
        names=subprocess.check_output(['git','ls-tree','-rz','--name-only','8edd49a'],cwd=repo).decode('utf-8').split('\0')
        support={}
        for name in names:
            if not name or not (name.endswith('CMakeLists.txt') or Path(name).suffix in ('.cmake','.in')):continue
            content=subprocess.check_output(['git','show','8edd49a:'+name],cwd=repo)
            dest=before/name;dest.parent.mkdir(parents=True,exist_ok=True)
            if dest.exists():assert dest.read_bytes()==content,name
            else:dest.write_bytes(content)
            support[name]=sha(dest)
        save(a.out/'old_support.json',support)
    names=subprocess.check_output(['git','ls-files','-z'],cwd=repo).decode('utf-8').split('\0')
    names+=subprocess.check_output(['git','ls-files','--others','--exclude-standard','-z'],cwd=repo).decode('utf-8').split('\0')
    for name in sorted(set(n for n in names if n and (Path(n).suffix in ('.c','.h','.in','.cmake') or n.endswith('CMakeLists.txt')))):
        src=repo/name;dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dest);r['sources'][name]=sha(src)
    shutil.copy2(__file__,a.out/'build_layer_monitor_v1.py')
    commands=[['cmake','-S',repo/'experiments/layer_monitor_v1','-B',build,'-G','Visual Studio 17 2022','-A','x64']]
    if a.phase=='old':commands[0].append('-DLM_OLD_ROOT='+before.as_posix())
    commands.append(['cmake','--build',build,'--config','Release','--parallel','2'])
    if a.phase=='old':commands[-1]+=['--target','layer_canonical_probe']
    if a.phase=='focused':commands[-1]+=['--target','layer_canonical_probe','layer_listen_checks','VslAtlasMonitor','layer_monitor_device']
    if a.phase=='old':
        (a.out/'probe').mkdir();commands+=[[build/'bin/Release/layer_canonical_probe.exe',a.out/'probe']]
    else:
        commands+=[['ctest','--test-dir',build,'-C','Release','--output-on-failure','--output-junit',a.out/'ctest.xml']]
        if a.phase=='focused':commands[-1]+=['-R','^layer_monitor_']
    for command in commands:
        argv=list(map(str,command));started=time.perf_counter();done=subprocess.run(argv,cwd=repo,capture_output=True,timeout=600)
        log=a.out/('command_%02d.log'%len(r['commands']));log.write_bytes(done.stdout+done.stderr)
        row=dict(argv=argv,exit_code=done.returncode,seconds=time.perf_counter()-started,log=log.name,sha256=sha(log));r['commands'].append(row)
        save(a.out/'report.json',r);print(row,flush=True)
        if done.returncode:raise RuntimeError(str(log))
    shutil.copy2(build/'CMakeCache.txt',a.out/'CMakeCache.txt');r['result']='passed'
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)

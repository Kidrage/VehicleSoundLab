"""Build an isolated CATCH LF adapter; preserve the existing real-time chain."""
import argparse,csv,json,shutil,subprocess,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(a.workspace/'tools/python_deps'))
from drive_evidence_v1.sources import sha
a.out.mkdir(parents=True,exist_ok=False)
for name in ('bin','renders','exact_sources'):(a.out/name).mkdir()
r=dict(result='running',commands=[],source_sha256={},old_C_H_unchanged=False)
def run(cmd):
    cmd=list(map(str,cmd));print(json.dumps(dict(running=cmd[:5])),flush=True)
    done=subprocess.run(cmd,cwd=repo,capture_output=True,timeout=300)
    log=f'command_{len(r["commands"]):02}.log';(a.out/log).write_bytes(done.stdout+done.stderr)
    r['commands'].append(dict(argv=cmd,returncode=done.returncode,log=log,sha256=sha(a.out/log)))
    assert done.returncode==0,log
    return done.stdout
try:
    index=a.workspace/'baselines/startup_catch_v1/docs/C文件索引.csv'
    with index.open(encoding='utf-8-sig') as stream:old={row['文件']:row['SHA-256'] for row in csv.DictReader(stream)}
    assert len(old)==456
    for name,digest in old.items():assert sha(repo/name)==digest,name
    r['old_C_H_unchanged']=True;r['old_C_H_count']=len(old)
    sources=[Path(__file__),*[repo/name for name in old]]
    for folder in ('src','modules','experiments'):
        sources.extend(x for x in (repo/folder).rglob('*') if x.is_file() and (x.suffix in ('.c','.h','.in') or x.name=='CMakeLists.txt'))
    sources.extend([repo/'CMakeLists.txt',repo/'handoff/CMakeLists.txt'])
    for source in dict.fromkeys(sources):
        name=source.relative_to(repo).as_posix();dest=a.out/'exact_sources'/name
        dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,dest);r['source_sha256'][name]=sha(source)
    build=repo/'build-catch-bloom-v1'
    run(['cmake','-S',repo/'experiments/catch_bloom_v1','-B',build,'-A','x64'])
    run(['cmake','--build',build,'--config','Release','--target','catch_bloom_probe','catch_bloom_checks','--parallel','4'])
    run(['ctest','--test-dir',build,'-C','Release','-R','^catch_bloom_contracts$','--output-on-failure'])
    for name in ('catch_bloom_probe.exe','catch_bloom_checks.exe'):shutil.copy2(build/'Release'/name,a.out/'bin'/name)
    r['binaries']={x.name:sha(x) for x in (a.out/'bin').iterdir()}
    placeholder=a.out/'zero.cb';placeholder.write_text('VSL_CATCH_BLOOM 1 1 2 2 .005 .035\n100 1 0\n',encoding='ascii')
    model=repo/'voices/startup_settle_v1/A start cabin settle.model';start=repo/'voices/startup_drive_v1/A cabin motion.start'
    prefix=a.out/'renders/base2'
    run([a.out/'bin/catch_bloom_probe.exe',model,start,placeholder,prefix,0,2])
    reference=a.workspace/'references/analysis/startup_catch_v1/render1/renders/scene_2_0.5'
    for old_name,new_name in [('mix.wav','base.wav'),('raw.wav','raw.wav'),('dna.wav','dna.wav'),('startup.wav','startup.wav')]:
        assert reference.with_name(reference.name+'_'+old_name).read_bytes()==prefix.with_name(prefix.name+'_'+new_name).read_bytes(),old_name
    assert prefix.with_name(prefix.name+'_mix.wav').read_bytes()==prefix.with_name(prefix.name+'_base.wav').read_bytes()
    for name,digest in r['source_sha256'].items():assert sha(repo/name)==digest,name
    r.update(result='isolated_adapter_built_and_checked',old_scene_four_stems_byte_equal=True,zero_mix_byte_equal=True,
             realtime_core_changed=False,device_test_repeated=False,UI_integrated=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:(a.out/'report.json').write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps({k:r[k] for k in ('result','old_C_H_count','binaries','old_scene_four_stems_byte_equal')}))

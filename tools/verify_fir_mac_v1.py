"""Measure all declared paired runs and exact original/new double outputs, no timing selection."""
import argparse,csv,json,shutil,subprocess,sys,time
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for name in ['workspace','out']:p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
from research_archive_v1 import load,save,sha
a.out.mkdir(parents=True,exist_ok=False)
r=dict(result='running',commands=[],sources={})
def command(label,args,timeout=240):
    start=time.perf_counter();done=subprocess.run(list(map(str,args)),cwd=repo,capture_output=True,timeout=timeout)
    path=a.out/(label+'.log');path.write_bytes(done.stdout+done.stderr)
    r['commands'].append(dict(label=label,args=list(map(str,args)),return_code=done.returncode,
      seconds=time.perf_counter()-start,log_sha256=sha(path)));save(a.out/'report.json',r)
    if done.returncode:raise RuntimeError(f'{label}: {done.returncode}; see {path}')
    return done.stdout
try:
    before=a.workspace/'references/analysis/fir_mac_v1/before1'
    assert load(before/'report.json')['result']=='original612C_H_and67voices_verified_before_mutation'
    expected=load(before/'C_files_sha256.json');changed=[k for k,v in expected.items() if sha(repo/k)!=v]
    assert changed==['modules/partitioned_fir/filter.c'],changed
    oldvoices=load(before/'voice_files_sha256.json');assert all(sha(repo/k)==v for k,v in oldvoices.items())
    allc=sorted(p for folder in ['src','modules','experiments','tests'] for p in (repo/folder).rglob('*') if p.suffix in ['.c','.h'])
    sources=[repo/'tools/verify_fir_mac_v1.py',repo/'research/fir_mac_v1_plan.json',repo/'tools/research_archive_v1.py']
    for folder in ['modules/partitioned_fir','modules/spectral_texture','modules/resonant_detail','experiments/fir_mac_v1']:
        sources.extend(p for p in (repo/folder).iterdir() if p.is_file())
    for path in sorted(set(sources)):
        name=path.relative_to(repo);dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,dest);r['sources'][name.as_posix()]=sha(path)
    build=repo/'build-fir-mac-v1';(a.out/'bin').mkdir()
    for name in ['fir_optimized_checks.exe','fir_scalar_checks.exe']:shutil.copy2(build/'Release'/name,a.out/'bin'/name)
    shutil.copy2(build/'CMakeCache.txt',a.out/'CMakeCache.txt')
    reference=before/'source/modules/partitioned_fir/filter.c';assert sha(reference)==load(before/'report.json')['reference_filter_sha256']
    r['reference_filter_sha256']=sha(reference)
    command('ctest',['ctest','--test-dir',build,'-C','Release','--output-on-failure','--output-junit',a.out/'ctest.xml'])
    profile=repo/'experiments/spectral_texture_v1/F2_fine_static.sfir'
    r['profile_sha256']=sha(profile)
    raw=command('paired_benchmark',[a.out/'bin/fir_optimized_checks.exe',profile,a.out/'paired.csv'])
    lines=[json.loads(line) for line in raw.decode().splitlines() if line.startswith('{')]
    assert len(lines)==6 and lines[-1]['result']=='passed' and lines[-1]['backend']=='SSE2'
    assert all(x['samples_exact'] for x in lines)
    with (a.out/'paired.csv').open() as f:rows=list(csv.DictReader(f))
    assert len(rows)==6000 and {(int(x['repeat']),int(x['block'])) for x in rows}=={(i,j) for i in range(5) for j in range(1200)}
    statistics=[]
    for i in range(5):
        group=[x for x in rows if int(x['repeat'])==i]
        old=np.array([float(x['old_ms']) for x in group]);new=np.array([float(x['new_ms']) for x in group])
        oc=np.array([float(x['old_cycles']) for x in group]);nc=np.array([float(x['new_cycles']) for x in group])
        statistics.append(dict(repeat=i,old_mean_ms=float(old.mean()),new_mean_ms=float(new.mean()),
          old_p99_ms=float(np.quantile(old,.99)),new_p99_ms=float(np.quantile(new,.99)),
          old_max_ms=float(old.max()),new_max_ms=float(new.max()),
          wall_reduction_fraction=float(1-new.sum()/old.sum()),cycle_reduction_fraction=float(1-nc.sum()/oc.sum())))
    save(a.out/'all_C_files_sha256.json',{path.relative_to(repo).as_posix():sha(path) for path in allc})
    r.update(result='paired_FIR_exactness_and_cost_observed',summary=lines[-1],repeats=statistics,
      old_C_H_unchanged=611,old_C_H_changed=changed,new_C_H=len(allc)-612,all_C_H=len(allc),old_voices_unchanged=len(oldvoices),
      all6000blocks_and_all5repeats_retained=True,paired_trace_sha256=sha(a.out/'paired.csv'),
      useful_cost_reduction=bool(np.median([x['cycle_reduction_fraction'] for x in statistics])>.05),
      source_and_profile_or_C_default_timbre_changed=False,full_driver_checked=False,hard_realtime=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(dict(result=r['result'],useful=r.get('useful_cost_reduction'),repeats=r.get('repeats')),flush=True)

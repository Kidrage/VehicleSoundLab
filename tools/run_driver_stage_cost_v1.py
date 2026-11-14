"""Compare actual plain/instrumented driving output before interpreting any stage costs."""
import argparse,csv,shutil,subprocess,sys,time
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for name in ['workspace','out']:p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
from research_archive_v1 import load,save,sha
a.out.mkdir(parents=True,exist_ok=False);r=dict(result='running',sources={},commands=[],cases=[])
try:
    before=a.workspace/'references/analysis/fir_mac_v1/before1';original=load(before/'C_files_sha256.json')
    voices=load(before/'voice_files_sha256.json');assert all(sha(repo/k)==v for k,v in original.items())
    assert all(sha(repo/k)==v for k,v in voices.items())
    names=[repo/'tools/run_driver_stage_cost_v1.py',repo/'research/driver_stage_cost_v1_plan.json',repo/'tools/research_archive_v1.py']
    names += [p for p in (repo/'experiments/driver_stage_cost_v1').iterdir() if p.is_file()]
    names += [repo/k for k in original]
    for path in names:
        name=path.relative_to(repo);dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,dest);r['sources'][name.as_posix()]=sha(path)
    build=repo/'build-driver-stage-cost-v1';(a.out/'bin').mkdir()
    for kind in ['plain','timed']:shutil.copy2(build/f'Release/stage_cost_{kind}.exe',a.out/f'bin/stage_cost_{kind}.exe')
    for name in ['CMakeCache.txt','wrapped_render.c']:shutil.copy2(build/name,a.out/name)
    for case in ['idle','drive']:
        outputs={}
        for kind in ['plain','timed']:
            trace=a.out/f'{case}_{kind}.csv';command=[a.out/f'bin/stage_cost_{kind}.exe',case,trace]
            start=time.perf_counter();done=subprocess.run(list(map(str,command)),cwd=repo,capture_output=True,timeout=90)
            log=a.out/f'{case}_{kind}.log';log.write_bytes(done.stdout+done.stderr)
            r['commands'].append(dict(command=list(map(str,command)),return_code=done.returncode,
              host_seconds=time.perf_counter()-start,log_sha256=sha(log)));save(a.out/'report.json',r)
            assert done.returncode==0,str(log)
            import json
            data=json.loads(done.stdout.decode());assert data['frames']==576000 and data['blocks']==1125
            raw=Path(str(trace)+'.f32');assert raw.stat().st_size==576000*2*4
            x=np.fromfile(raw,dtype='<f4');assert np.isfinite(x).all()
            data.update(raw_sha256=sha(raw),trace_sha256=sha(trace),raw_file=raw.name,trace_file=trace.name)
            outputs[kind]=data
        assert outputs['plain']['raw_sha256']==outputs['timed']['raw_sha256']
        assert (a.out/outputs['plain']['raw_file']).read_bytes()==(a.out/outputs['timed']['raw_file']).read_bytes()
        stages=sorted((v for v in outputs['timed']['metrics'] if v['stage']!='empty_timer'),key=lambda v:v['seconds'],reverse=True)
        row=dict(case=case,plain=outputs['plain'],timed=outputs['timed'],all1152000_float_samples_byte_exact=True,
          ordered_stages=stages,measurement_overhead_not_removed=True)
        r['cases'].append(row)
        print(dict(case=case,plain_seconds=outputs['plain']['total_seconds'],timed_seconds=outputs['timed']['total_seconds'],
          output_exact=True,top_stages=stages[:4]),flush=True)
    r.update(result='actual_driver_stages_observed_with_exact_audio',old612C_H_exact=True,old67voices_exact=True,
      pending_idle_audio_changed=False,native_or_take_defaults_changed=False,hard_realtime=False,
      attribution_limit='Stage timing includes QPC and instrumentation/cache/scheduling effects; not unbiased disjoint plain-time fractions.')
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)

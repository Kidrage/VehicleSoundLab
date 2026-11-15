"""One declared known-source qualification of recorded phase context."""
import argparse
import os
import shutil
import sys
from pathlib import Path
from research_archive_v1 import save,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('workspace','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from exterior_clock_v1.warp import warp,polish
    from recorded_phase_context_v1.mapping import extend
    from recorded_phase_context_v1.observation import ContextRejected
    from recorded_phase_context_v1.metrics import heldout
    from recorded_phase_context_v1.fixtures import specs,cycles,formula
    repo=Path(__file__).resolve().parents[1];a.out.mkdir(parents=True,exist_ok=False)
    names=['tools/run_recorded_phase_context_known_v1.py','tools/exterior_clock_v1/warp.py',
           'research/recorded_phase_context_v1_plan.json']
    names.extend(p.relative_to(repo).as_posix() for p in (repo/'tools/recorded_phase_context_v1').glob('*.py'))
    r=dict(result='running',cases=[],rejections=[],sources={},material_read=False)
    try:
        for name in names:
            path=a.out/'exact_sources'/name;path.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(repo/name,path);r['sources'][name]=sha(path)
        t=np.arange(4*48000)/48000
        clock=np.arange(.25,3.75+.0025,.005)
        base=None
        for name,spec in specs():
            native=formula(t,spec)
            # Only the coarse root/slope, biased by0.8percent. PM truth and all
            # independent stereo laws remain unavailable to the estimator.
            hz=(spec['root']+spec['slope']*clock)*1.008
            aperture=[2-9/(spec['root']+2*spec['slope']),2+9/(spec['root']+2*spec['slope'])]
            coarse,pos,initial=warp(native,0,clock,hz,*aperture)
            old,where,phase=polish(native,0,coarse,pos,5,initial['source_cutoff_hz'])
            arrays,info=extend(native,0,clock,hz,aperture,old,where,phase['source_cutoff_hz'])
            q=cycles(arrays['positions'],spec)-arrays['sample_indices']/1024
            cycle_std=float(np.std(q))
            ideal=formula(arrays['positions'],spec)
            error=float(np.linalg.norm(arrays['audio']-ideal)/np.linalg.norm(ideal))
            carrier=heldout(arrays)
            minimum=min(min(v['coherence']) for x in carrier.values() for v in x.values())
            qualified=bool(cycle_std<.002 and error<.005 and minimum>.99)
            file=a.out/(name+'.npz')
            np.savez_compressed(file,native=native,clock_times=clock,root_hz=hz,aperture=aperture,**arrays)
            r['cases'].append(dict(label=name,spec=spec,file=file.name,sha256=sha(file),
                info=info,cycle_residual_std=cycle_std,analytic_wave_NRMSE=error,
                heldout=carrier,qualified=qualified))
            if name=='constant':base=(spec,native,clock,hz,aperture,old,where,phase)
            save(a.out/'report.json',r)
            print(name,qualified,'cycles',cycle_std,'wave',error,'coherence',minimum,flush=True)
        spec,native,clock,hz,aperture,old,where,phase=base
        tests=[('missing_reference',dict(reference_gain=0.),'weak_or_missing_reference'),
               ('weak_reference',dict(reference_gain=1e-6),'weak_or_missing_reference'),
               ('gapped_reference',dict(gap=True),'weak_or_missing_reference')]
        for name,change,expected in tests:
            altered=formula(t,dict(spec,**change));reason=None
            try:extend(altered,0,clock,hz,aperture,old,where,phase['source_cutoff_hz'])
            except ContextRejected as e:reason=str(e)
            file=a.out/(name+'.npz');np.savez_compressed(file,native=altered)
            r['rejections'].append(dict(label=name,expected=expected,reason=reason,
                file=file.name,sha256=sha(file),qualified=reason==expected))
        tests=[('unsupported_clock',dict(clock_times=clock[(clock>aperture[0]-.002)&(clock<aperture[1]+.002)],
                    root_hz=hz[(clock>aperture[0]-.002)&(clock<aperture[1]+.002)])),
               ('unsupported_FIR',dict(audio=native[round((aperture[0]-.005)*48000):round((aperture[1]+.005)*48000)],
                    source_start=round((aperture[0]-.005)*48000)/48000)),
               ('altered_original_coordinate',dict(original_positions=where+1e-8)),
               ('altered_original_stereo',dict(original_audio=old[:,::-1].copy()))]
        kwargs=dict(audio=native,source_start=0,clock_times=clock,root_hz=hz,aperture=aperture,
                    original_audio=old,original_positions=where,cutoff=phase['source_cutoff_hz'])
        for name,change in tests:
            reason=None
            try:extend(**dict(kwargs,**change))
            except ValueError as e:reason=str(e)
            r['rejections'].append(dict(label=name,reason=reason,qualified=bool(reason)))
        r.update(result='recorded_phase_context_known_measured',
            all_qualified=all(c['qualified'] for c in r['cases']+r['rejections']),
            no_source_or_runtime_qualification=True)
        save(a.out/'report.json',r)
    except BaseException as e:
        r.update(result='failed',error=repr(e));save(a.out/'report.json',r);raise


if __name__=='__main__':main()

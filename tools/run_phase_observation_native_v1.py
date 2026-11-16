"""Extend saved analytic fixtures through frozen native normalization; no real fitting."""
import argparse
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load,save,sha


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('workspace','out'):parser.add_argument('--'+name,type=Path,required=True)
    a=parser.parse_args()
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from exterior_clock_v1.warp import warp
    from phase_observation_native_v1.source import coordinate,evaluate,instantaneous
    from phase_observation_native_v1.observe import observe,temporal
    from c1_registered_source_v1.binding import protected
    repo=Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True,exist_ok=False)
    r=dict(result='running',sources={},inputs={},cases=[],
        truth_contract='per-variant instantaneous carrier64 envelope in observer coordinates')
    try:
        protected(a.workspace,repo)
        names=('research/phase_observation_native_v1_plan.json','tools/run_phase_observation_native_v1.py',
            'tools/audit_phase_observation_native_v1.py','tools/phase_observation_native_v1/__init__.py',
            'tools/phase_observation_native_v1/source.py','tools/phase_observation_native_v1/observe.py',
            'tools/sound_dna/windowed.py','tools/exterior_clock_v1/warp.py','tools/research_archive_v1.py')
        for name in names:
            dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(repo/name,dest);r['sources'][name]=sha(dest)
        plan=load(repo/names[0]);g=plan['geometry'];gate=plan['checks']
        parent=a.workspace/'references/analysis/conditional_phase_time_v1'
        known,proof=load(parent/'known1/report.json'),load(parent/'known_audit1/report.json')
        assert proof['result']=='independent_conditional_time_known_audit_passed'
        assert proof['producer_sha256']==sha(parent/'known1/report.json')
        for p in (parent/'known1/report.json',parent/'known_audit1/report.json'):r['inputs'][str(p)]=sha(p)
        assert sha(repo/'tools/sound_dna/windowed.py')==known['sources']['tools/sound_dna/windowed.py']
        ancestor_path=a.workspace/'baselines/coefficient_geometry_v1/evidence/real1/report.json'
        ancestor=load(ancestor_path);r['inputs'][str(ancestor_path)]=sha(ancestor_path)
        assert sha(repo/'tools/exterior_clock_v1/warp.py')==ancestor['sources']['tools/exterior_clock_v1/warp.py']
        for kind in plan['known_cases']+plan['native_extra_cases']:
            source_kind=kind if kind in plan['known_cases'] else 'static'
            path=parent/'known1'/(source_kind+'.npz')
            old=next(v for v in known['cases'] if v['label']==source_kind)
            assert sha(path)==old['sha256'];r['inputs'][str(path)]=sha(path)
            keys=('orders','amplitudes','phases','root_hz','modulation_cycles_per_cycle','modulation_depth','PM_depth')
            with np.load(path) as f:spec={k:f[k] for k in keys};saved_audio=f['audio']
            spec['kind']=source_kind
            fixture_error=float(abs(evaluate(spec,np.arange(len(saved_audio)))-saved_audio).max())
            assert fixture_error<gate['saved_integer_fixture_FS']
            source_depth=g['matching_clock_depth'] if kind=='static_matching_variable_clock' else 0.
            clock_depth=source_depth if kind=='static_matching_variable_clock' else g['mismatched_clock_depth'] if kind=='static_mismatched_clock' else 0.
            rate=g['native_rate'];start=g['normalized_start'];stop=start+g['cycles']/g['root_hz']
            native_times=np.arange(round((stop+g['context_seconds'])*rate)+1)/rate
            native_coordinate=coordinate(native_times,g,source_depth)
            native=evaluate(spec,native_coordinate)
            times=np.arange(round(start*rate),round(stop*rate)+1)/rate
            hz=g['root_hz']*(1+clock_depth*np.sin(2*np.pi*g['clock_frequency_Hz']*times))
            audio,positions,metadata=warp(native,0.,times,hz,start,stop)
            q=coordinate(positions,g,source_depth);clock_q=coordinate(positions,g,clock_depth)
            clock_error=float(abs(clock_q-np.arange(len(q))).max())
            assert clock_error<gate['analytic_clock_virtual_samples']
            query=evaluate(spec,q);canonical=evaluate(spec,np.arange(len(q)))
            bridge_error=float(abs(audio-query).max())
            assert bridge_error<gate['native_bridge_approximation_FS']
            arrays=dict(native_times=native_times,native_coordinate=native_coordinate,native_audio=native,
                positions=positions,source_query_coordinate=q,clock_times=times,clock_hz=hz,
                native_normalized_audio=audio,query_exact_audio=query,canonical_audio=canonical,
                **{key:spec[key] for key in keys})
            row=dict(label=kind,source_kind=source_kind,source_clock_depth=source_depth,
                observer_clock_depth=clock_depth,native_frames=len(native),normalized_frames=len(audio),
                fixture_saved_sample_error_FS=fixture_error,clock_query_error_virtual_samples=clock_error,
                native_bridge_error_FS=bridge_error,
                canonical_difference_FS=float(abs(audio-canonical).max()),
                inherited_warp=metadata,observations=[])
            for cycles in (2,4,8):
                starts=np.arange(0,len(audio)-1024*cycles+1,256)
                centers=starts+512*cycles
                scale=.07
                for variant,value in (('native',audio),('query',query),('canonical',canonical)):
                    z=observe(value,cycles);arrays[f'{variant}_cycles{cycles}']=z
                    # Envelopes are referenced to the OBSERVER carrier phase.
                    source_centers=centers if variant=='canonical' else q[centers]
                    truth=instantaneous(spec,source_centers)*np.exp(2j*np.pi*64*(source_centers-centers)/1024)[:,None]
                    arrays[f'truth_{variant}_cycles{cycles}']=truth
                    row['observations'].append(dict(variant=variant,cycles=cycles,hop=256,rows=len(z),
                        observed=temporal(z[:,63],scale),truth=temporal(truth,scale),
                        observed_prefix40=temporal(z[:40,63],scale),truth_prefix40=temporal(truth[:40],scale),
                        hop1024_subset=temporal(z[::4,63],scale)))
                arrays[f'starts_cycles{cycles}']=starts
            output=a.out/(kind+'.npz');np.savez_compressed(output,**arrays)
            row['sha256']=sha(output);r['cases'].append(row);save(a.out/'report.json',r)
            print('NATIVE_OBSERVATION_CONTROL',kind,'bridgeFS',bridge_error,'clockSamples',clock_error,flush=True)
        r.update(result='native_phase_observation_known_controls_measured',all_bridge_gates_passed=True,
            no_vehicle_refit_or_new_training_or_C_change=True,new_C1_source_eligible_for_statistics=False,
            no_clock_estimator_or_naturalness_or_hearing_qualification=True)
        save(a.out/'report.json',r);print(r['result'],flush=True)
    except BaseException as error:r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise


if __name__=='__main__':main()

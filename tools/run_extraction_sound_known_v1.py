"""Deterministic sound-meter controls, while the immutable real extraction runs."""
import argparse
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import save,load,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('workspace','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from extraction_sound_v1.measure import measure
    from extraction_sound_v1.compare import compare
    from extraction_sound_v1.fixtures import fixtures
    repo=Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True,exist_ok=False)
    r=dict(result='running',cases=[],sources={},inputs={},real_material_read=False)
    try:
        names=['tools/run_extraction_sound_known_v1.py','tools/audit_extraction_sound_known_v1.py',
            'research/extraction_sound_v1_plan.json','research/extraction_sound_v2_plan.json',
            'tools/diagnose_extraction_sound_roundoff_v1.py','tools/audit_extraction_sound_composed_v2.py']
        names.extend(p.relative_to(repo).as_posix() for p in (repo/'tools/extraction_sound_v1').glob('*.py'))
        for name in names:
            dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(repo/name,dest);r['sources'][name]=sha(dest)
        spec=a.workspace/'references/analysis/waveform_file_real_v1/real1/run_spec.json'
        r['inputs'][str(spec)]=sha(spec);live=load(spec)
        assert all(sha(repo/name)==h for name,h in live['sources'].items())
        known=list(fixtures())
        rng=np.random.default_rng(739)
        compact=rng.normal(0,.02,(384,2))
        compact[:,0]+=.04+.03*(-1.)**np.arange(len(compact))
        known.append(('compact_all_bins',compact,65536))
        for name,audio,rate in known:
            size,hop=(128,64) if name=='compact_all_bins' else (4096,256)
            orders=np.arange(1,289) if rate==65536 and size==4096 else None
            result=measure(audio,rate,size=size,hop=hop,orders=orders,root=64 if orders is not None else None)
            energy=float(np.max(result['windowed_time_Gram']))
            assert np.max(abs(result['full_Gram'].real-result['windowed_time_Gram']))<=2e-11*max(energy,np.finfo(float).tiny)
            assert np.max(abs(result['broad_Gram'].sum(axis=1)-result['full_Gram']))<=2e-11*max(energy,np.finfo(float).tiny)
            if name in ('silent_right','zero'):
                assert np.count_nonzero(result['broad_mean_power'][:,1])==0
                assert np.count_nonzero(result['broad_coherence_defined'])==0
            if name=='zero':assert np.count_nonzero(result['broad_power_defined'])==0
            if name=='weak_HF':
                assert result['broad_power_defined'][5].all() and np.max(result['broad_mean_power'])<1e-24
                assert result['broad_power_resolved'].all()
            if name=='mono':assert np.count_nonzero(result['broad_mid_side'][:,:,1])==0
            if name=='inverted_mono':assert np.count_nonzero(result['broad_mid_side'][:,:,0])==0
            path=a.out/(name+'.npz')
            np.savez_compressed(path,audio=audio,rate=rate,size=size,hop=hop,**result)
            if name=='unequal_phase':
                scaled=measure(audio*1.7,rate,orders=orders,root=64)
                change=compare(scaled,result)
                expected=20*np.log10(1.7)
                assert np.max(abs(np.array(change['broad']['power_change_dB'])-expected))<2e-10
                for prefix in ('broad','line'):
                    assert np.array_equal(result[prefix+'_power_resolved'],scaled[prefix+'_power_resolved'])
                    original=result[prefix+'_power_uncertainty']
                    delta=scaled[prefix+'_power_uncertainty']-original*1.7**2
                    assert np.max(abs(delta))/np.max(original*1.7**2)<2e-10
                save(a.out/'known_scaled_comparison.json',change)
            if name=='zero':
                nonzero=measure(np.column_stack((np.ones(len(audio))*.01,np.ones(len(audio))*.02)),rate,orders=orders,root=64)
                change=compare(nonzero,result)
                assert all(x is None for row in change['broad']['power_change_dB'] for x in row)
                assert all(x is None for x in change['broad']['complex_coherence_change'])
                save(a.out/'zero_reference_comparison.json',change)
            r['cases'].append(dict(label=name,file=path.name,sha256=sha(path),frames=len(audio),rate=rate,size=size,hop=hop,
                line_diagnostic=orders is not None,windows=len(result['starts'])))
            save(a.out/'report.json',r)
            print('SOUND_METER',name,len(result['starts']),flush=True)
        assert all(sha(repo/name)==h for name,h in live['sources'].items())
        r.update(result='extraction_sound_known_measured',live_fit_sources_unchanged=True,
            all_defined_and_exact_zero_controls_passed=True,all_material_and_C_and_hearing_unchanged=True)
        save(a.out/'report.json',r)
    except BaseException as error:
        r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise


if __name__=='__main__':main()

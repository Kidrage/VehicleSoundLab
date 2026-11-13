"""Independent analytic fixture waveforms and known-outcome semantics only."""
import argparse,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','input','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
from research_archive_v1 import load,save,sha
a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_check.py')
r=dict(result='running',fixtures=0,maximum_sample_error=0.)
try:
    report=load(a.input/'report.json');assert report['result']=='all48_upper_inventory_rejection_census_complete'
    n=12000;t=np.arange(n)/48000
    carrier=lambda hz,phase:np.exp(1j*(2*np.pi*hz*t+phase)).real
    base=.4*carrier(300,.23)
    high=.0001*carrier(5132,.7)+.00008*carrier(10012,-.3)
    stereo=lambda x:np.stack([x,.67*x],axis=1)
    noise=np.random.default_rng(149921).normal(size=(n,2))*1e-6
    quiet=stereo(base+high)+noise
    expected=dict(quiet_upper=quiet,quiet_upper_gain=.013*quiet,
        moving_upper=stereo(base+.0001*np.exp(1j*(2*np.pi*5132*t+np.pi*80*t*t+.7)).real)+noise,
        missing_with_neighbor=stereo(base+.0001*carrier(5192,.7))+noise,
        pure_low_numerical_tail=stereo(base),silence=np.zeros((n,2)))
    for seed in [149921,277139,381611]:
        gaussian=np.random.default_rng(seed).normal(size=(n,2))*.01
        expected[f'noise_independent_{seed}']=gaussian
        expected[f'noise_mono_{seed}']=stereo(gaussian[:,0])
    assert set(expected)==set(report['known'])
    for name,x in expected.items():
        actual=np.load(a.input/'known'/(name+'.npz'))['audio']
        error=float(abs(actual-x).max());assert error<1e-12,(name,error)
        r['maximum_sample_error']=max(r['maximum_sample_error'],error);r['fixtures']+=1
    rows=report['known'];control=report['controls']
    for target in [5132,10012]:
        candidates=[p for p in rows['quiet_upper']['peaks'] if abs(p['frequency_hz']-target)<4 and p['local_candidate']]
        assert len(candidates)==1 and not candidates[0]['old_floor_ok']
    first=[p for p in rows['quiet_upper']['peaks'] if p['local_candidate']]
    scaled=[p for p in rows['quiet_upper_gain']['peaks'] if p['local_candidate']]
    assert [p['bin'] for p in first]==[p['bin'] for p in scaled]
    assert all(abs(x['frequency_hz']-y['frequency_hz'])<1e-7 for x,y in zip(first,scaled))
    assert len([p for p in rows['moving_upper']['peaks'] if p['local_candidate'] and abs(p['frequency_hz']-5142)<4])==1
    assert not any(p['local_candidate'] and abs(p['frequency_hz']-5132)<4 for p in rows['missing_with_neighbor']['peaks'])
    assert not rows['silence']['peaks']
    counts={name:sum(p['local_candidate'] for p in row['peaks']) for name,row in rows.items() if name.startswith('noise_')}
    assert all(count>0 for count in counts.values()) and counts==control['noise_candidate_counts']
    assert sum(p['local_candidate'] for p in rows['pure_low_numerical_tail']['peaks'])==control['numerical_tail_candidates']
    assert control['quiet_lines_recovered']==2 and control['old_floor_rejects_both'] and control['gain_invariant']
    assert control['moving_line_recovered'] and control['no_forced_missing_slot'] and control['local_peak_inventory_is_NOT_source_detector']
    r.update(result='all12_known_waveforms_and_outcomes_verified',input_report_sha256=sha(a.input/'report.json'),
             local_candidate_counts_not_engine_identity=True,scope='Known fixtures only; real all48census audited separately.')
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(r,flush=True)

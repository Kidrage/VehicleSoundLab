"""Known-first independent scalar decoding and full signed interference audit."""
import argparse
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load,save,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('workspace','study','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from phase_input_paths_v1.audit_oracle import scalar_phase,observe,budget
    repo=Path(__file__).resolve().parents[1];a.out.mkdir(parents=True,exist_ok=False)
    shutil.copy2(__file__,a.out/'executed_audit.py');shutil.copy2(repo/'tools/phase_input_paths_v1/audit_oracle.py',a.out/'executed_oracle.py')
    report=dict(result='running',cases=0,scalar_queries=0,maximum_phase_error=0.,maximum_Gram_scaled_error=0.,maximum_wave_error=0.)
    try:
        old=load(a.study/'report.json');assert old['result']=='phase_input_known_ready'
        for name,digest in old['sources'].items():assert sha(repo/name)==sha(a.study/'exact_sources'/name)==digest
        plan=load(a.study/'exact_sources/research/phase_input_paths_v1_plan.json')
        for row in old['cases']+[dict(name='cancellation',**old['cancellation'])]:
            path=a.study/row['file'];assert sha(path)==row['sha256']
            with np.load(path) as z:
                if row['name']!='cancellation':
                    truth=np.empty_like(z['delta'])
                    for n,(product,uniform) in enumerate(zip(z['product'],z['uniform'])):
                        for j,(pv,uv) in enumerate(((1.,.5),(product,.5),(1.,uniform),(product,uniform))):
                            truth[n,j]=scalar_phase(pv,uv,z['knots'],z['cdf'],z['low'],z['high']);report['scalar_queries']+=1
                    error=float(abs(truth-z['delta']).max());assert error<2e-12
                    report['maximum_phase_error']=max(report['maximum_phase_error'],error)
                    n=np.arange(len(truth));common=.17*np.sin(2*np.pi*n/5000)
                    amplitude=np.column_stack([1+.1*np.sin(n/400),.7+.08*np.cos(n/600)])
                    wave=np.zeros_like(z['counterfactual_audio'])
                    for j in range(4):
                        for c,sign in ((0,1),(1,-1)):
                            for order,weight in ((70,.7),(110,.5),(140,.4),(190,.3)):
                                wave[:,j,c]+=weight*amplitude[:,c]*np.cos(2*np.pi*n/1024*order+common+sign*truth[:,j]/2)
                    error=float(abs(wave-z['counterfactual_audio']).max());assert error<2e-12
                    report['maximum_wave_error']=max(report['maximum_wave_error'],error)
                    base,p,u,joint=np.moveaxis(wave,1,0)
                    terms=np.stack([base,p-base,u-base,joint-p-u+base],axis=1)
                    assert abs(terms-z['term_audio']).max()<2e-12
                    assert abs(terms.sum(axis=1)-joint).max()<2e-12
                measured=observe(z['term_audio'],64.,plan['bands_Hz'])
                for prefix in ('line','broad'):
                    m=measured[prefix+'_Gram'];scales=np.maximum(np.diagonal(m,axis1=-2,axis2=-1).real.sum(axis=-1).max(axis=0),1e-24)
                    error=float((abs(m-z[prefix+'_Gram'])/scales[None,:,None,None]).max());assert error<2e-10
                    report['maximum_Gram_scaled_error']=max(report['maximum_Gram_scaled_error'],error)
                    values=budget(m)
                    assert abs(values['self_power'].sum(axis=1)+values['signed_pairs'].sum(axis=1)-values['total_power']).max()<2e-12
                    if row['name']!='cancellation':
                        for key,value in values.items():assert abs(value-z[prefix+'_'+key]).max()<2e-12
                    else:
                        # B-B+.3B+.2B=.5B. Full Gram includes negative interference.
                        assert abs(values['total_power']-.25*values['self_power'][:,0]).max()<2e-12
                        assert (values['signed_pairs']<0).any()
                scale=max(float(np.diagonal(measured['time_energy_Gram'],axis1=-2,axis2=-1).sum(axis=-1).max()),1e-24)
                for key in ('all_frequency_Gram','time_energy_Gram'):assert abs(measured[key]-z[key]).max()/scale<2e-10
                assert abs(measured['all_frequency_Gram'].real-measured['time_energy_Gram']).max()/scale<2e-10
            report['cases']+=1
        assert report['cases']==9
        report.update(result='independent_phase_input_known_passed',producer_sha256=sha(a.study/'report.json'),
            auditor_sha256=sha(__file__),oracle_sha256=sha(repo/'tools/phase_input_paths_v1/audit_oracle.py'),source_audio_read=False)
        save(a.out/'report.json',report);print(report,flush=True)
    except BaseException as e:
        report.update(result='failed',error=repr(e));save(a.out/'report.json',report);raise


if __name__=='__main__':main()

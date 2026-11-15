"""Independent original stereo oracle for equilibration, plus vector bookkeeping.

The original FFT-normal component is crosschecked against the independent full
operator. The other components receive bookkeeping checks, not a second native
factorization proof; their exact executed sources remain frozen separately.
"""
import argparse
import os
import shutil
import sys
from pathlib import Path
from research_archive_v1 import load,save,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('workspace','original','normal','probe','out'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args()
    for n in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[n]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from scipy import linalg
    from observer_supported_v1.audit_oracle import matrices,metric
    from observer_complete_v1.audit_oracle import full_frame
    a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_audit.py')
    repo=Path(__file__).resolve().parents[1]
    for n in ('tools/observer_supported_v1/audit_oracle.py','tools/observer_complete_v1/audit_oracle.py',
              'tools/observer_frequency_v1/reduced_oracle.py'):
        dest=a.out/'exact_oracles'/n;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/n,dest)
    r=dict(result='running',cases=[],inputs={})
    def read(folder):
        path=folder/'report.json';r['inputs'][str(path)]=sha(path);return load(path)
    def bind_sources(folder,report):
        for n,h in report.get('sources',{}).items():assert sha(folder/'exact_sources'/n)==h
        for n,h in report.get('inputs',{}).items():assert sha(n)==h
    def data(folder,case):
        path=folder/case['file'];assert sha(path)==case['sha256'];r['inputs'][str(path)]=sha(path)
        with np.load(path) as z:return {n:z[n] for n in z.files}
    try:
        original,normal,probe=[read(folder) for folder in (a.original,a.normal,a.probe)]
        for folder,report in ((a.original,original),(a.normal,normal),(a.probe,probe)):bind_sources(folder,report)
        assert original['backend']=='banded' and normal['result']=='waveform_banded_complete_normal_components_diagnosed'
        assert probe['result']=='waveform_banded_equilibration_known_probe_measured' and len(probe['cases'])==5
        parents={c['label']:c for c in original['cases'] if c['kind']=='Hann'}
        normals={c['label']:c for c in normal['cases']}
        for case in probe['cases']:
            old=data(a.original,parents[case['label']]);z=data(a.probe,case);d=data(a.normal,normals[case['label']])
            profile=metric(old['audio'],64.)
            A,b,Phi,R,count=matrices(old['positions'],old['orders'],old['scale'],old['audio'],profile)
            assert abs(A-old['original_A']).max()/max(1.,abs(A).max())<2e-8
            L=np.linalg.cholesky(R);inv=linalg.solve_triangular(L.T,np.eye(len(R)))
            B,target=A[:count],b[:count];G=np.vstack((B@inv,np.eye(len(R))))
            rhs=np.r_[target,np.zeros(len(R))];normG=np.linalg.norm(G)
            def observed_model(wave,q):
                rows,_=full_frame(wave);rows=rows[profile['keep']]*profile['amplitude']*profile['weights'][None,:,None]
                model=np.r_[wave.ravel()/profile['sigma'],rows.real.ravel(),rows.imag.ravel(),L.T@q]
                return model,G.T@model
            q=z['q'].ravel();assert np.array_equal(q,z['q_interleaved'])
            model,g=observed_model(z['wave_model_residual'],q)
            stable=float(np.linalg.norm(g)/max(normG*np.linalg.norm(model),1e-300))
            backward=float(np.linalg.norm(G@(L.T@q)-rhs-model)/max(np.linalg.norm(rhs),1e-300))
            reference=linalg.lstsq(A,b,lapack_driver='gelsd')[0]
            relative=float(np.linalg.norm(q-reference)/max(np.linalg.norm(reference),1e-300))
            e=A@q-b;gradient=float(np.linalg.norm(A.T@e)/max(np.linalg.norm(A.T@b),1e-300));J=float(e@e)
            residual=B@q-target;gaps={}
            for tag in ('residual','representer'):
                certificate=case[tag+'_certificate']
                if tag=='residual':
                    factor=certificate['residual_dual_scale']
                    delta=q+factor*linalg.solve(R,B.T@residual,assume_a='pos')
                    gap=float((1-factor)**2*(residual@residual)+delta@R@delta)
                else:
                    delta=q+linalg.solve(R,B.T@residual,assume_a='pos')
                    gap=float(delta@R@delta)
                assert abs(gap-certificate['gap_upper_bound'])<2e-8
                gaps[tag]=dict(gap=gap,passed=bool(gap<=1e-6*J+1e-10))
            qualified=bool(relative<2e-7 and gradient<2e-7 and stable<=1e-11 and backward<=1e-11
                and all(c['passed'] for c in gaps.values()) and case['solver']['stable_root_guard_passed'])
            assert qualified==case['qualified']
            den=float(d['denominator'])
            keys=('FFT_minus_stored','stored_minus_factored','factored_minus_model')
            assert np.max(abs(sum(d[k] for k in keys)-(d['original_FFT']-d['root_model'])))<1e-12
            for tag in ('original_FFT','stored_Gram','factored_Gram','root_model'):
                expected=float(np.linalg.norm(d[tag])/den)
                assert expected==normals[case['label']]['normalized_normal_actions'][tag]
            original_model,original_g=observed_model(old['wave_model_residual'],old['q'].ravel())
            discrepancy=float(np.linalg.norm(original_g-d['original_FFT'].ravel())/den)
            assert discrepancy<2e-13
            r['cases'].append(dict(label=case['label'],qualified=qualified,
                independent_stable_complete_normal=stable,backward=backward,gradient=gradient,dense_relative_error=relative,
                certificates=gaps,original_FFT_component_oracle_discrepancy=discrepancy,
                other_component_vector_bookkeeping_verified=True))
            print('AUDITED EQUILIBRATION',case['label'],qualified,stable,flush=True)
        assert len(r['cases'])==5 and sum(c['qualified'] for c in r['cases'])==probe['pass_count']==4
        r.update(result='independent_waveform_banded_diagnosis_verified',equilibration_pass_count=4,
            equilibration_failure_retained='delayed_right',producer_sha256=sha(a.probe/'report.json'),
            original_gate_not_changed=1e-11,full_suite_or_source_or_runtime_NOT_qualified=True)
        save(a.out/'report.json',r)
    except BaseException as error:
        r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise


if __name__=='__main__':main()

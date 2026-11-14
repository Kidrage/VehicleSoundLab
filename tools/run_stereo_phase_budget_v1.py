"""Frozen stereo-debt decomposition and exact observer-window null, no new preset."""
import argparse
import hashlib
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load,save,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('workspace','out'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--stage',choices=['known','real'],required=True)
    for n in ('known','known-audit'):p.add_argument('--'+n,type=Path)
    a=p.parse_args();repo=Path(__file__).resolve().parents[1]
    for n in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[n]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from scipy.special import ndtri
    from scipy.stats import qmc
    from stereo_phase_budget_v1.budget import measure,marginal_moment,decompose
    from stereo_phase_budget_v1.window import covariance,observed
    from relative_phase_v1.coordinates import decode
    from radial_copula_v1.observe import describe,json_summary
    a.out.mkdir(parents=True,exist_ok=False)
    report=dict(result='running',stage=a.stage,cases=[],inputs={},sources={})
    try:
        sources=['research/stereo_phase_budget_v1_plan.json','tools/run_stereo_phase_budget_v1.py',
                 'tools/stereo_phase_budget_v1/budget.py','tools/stereo_phase_budget_v1/window.py',
                 'tools/relative_phase_v1/coordinates.py','tools/radial_copula_v1/quantiles.py',
                 'tools/radial_copula_v1/observe.py','tools/sound_dna/windowed.py']
        for n in sources:
            out=a.out/'exact_sources'/n;out.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(repo/n,out);report['sources'][n]=sha(out)
        plan=load(repo/'research/stereo_phase_budget_v1_plan.json')
        def consume(path):report['inputs'][str(path)]=sha(path);return path
        def array_summary(d):
            return {k:(np.column_stack([v.real,v.imag]).tolist() if np.iscomplexobj(v) else v.tolist()) for k,v in d.items()}
        def identity(d):
            error=abs(d['error']-sum(d[k] for k in ['amplitude_product','phase_marginal','association','denominator'])).max()
            assert error<plan['checks']['complex_identity_absolute']
            assert abs(d['phase_marginal']-d['phase_quantile_bias']-d['phase_QMC_discrepancy']).max()<plan['checks']['complex_identity_absolute']
            return float(error)
        if a.stage=='known':
            ones=np.ones((2,1,2));zero=np.zeros_like(ones)
            common=np.broadcast_to(np.array([0.,-.7]),ones.shape)
            equal=np.array([[[.5,.5]],[[1.5,1.5]]])
            opposed=equal[...,::-1].copy();opposed[:,0,1]=opposed[::-1,0,1]
            sqrt=np.sqrt(np.array([1.,2.]))[:,None,None]*ones
            phase=np.zeros_like(ones);phase[1,0,0]=np.pi/2
            fixtures=dict(equal=(ones,common,ones.copy(),common.copy()),
                phase_only=(ones,zero,ones,np.broadcast_to(np.array([.4,0.]),ones.shape)),
                amplitude_product_only=(equal,common,opposed,common),
                association_only=(sqrt,phase,sqrt,phase[::-1].copy()),
                denominator_only=(ones,zero,np.array([[[.5,1.]],[[1.5,1.]]]),zero),
                signed_cancellation=(ones,common,2*ones,common),
                silent_rejected=(zero,zero,ones,zero))
            for name in plan['known']:
                A,P,B,Q=fixtures[name];folder=a.out/name;folder.mkdir()
                np.savez_compressed(folder/'inputs.npz',source_amplitude=A,source_phase=P,model_amplitude=B,model_phase=Q)
                if name=='silent_rejected':
                    try:decompose(measure(A,P),measure(B,Q),[np.arange(1)])
                    except ValueError:pass
                    else:raise AssertionError('Silent coherence must be explicitly undefined')
                    row=dict(label=name,undefined_coherence_rejected=True)
                else:
                    d=decompose(measure(A,P),measure(B,Q),[np.arange(1)])
                    only={'phase_only':'phase_marginal','amplitude_product_only':'amplitude_product',
                          'association_only':'association','denominator_only':'denominator'}
                    if name in only:
                        assert abs(d[only[name]][0])>.05
                        assert all(abs(d[k][0])<2e-12 for k in ['phase_marginal','amplitude_product','association','denominator'] if k!=only[name])
                    if name=='signed_cancellation':assert abs(d['error'][0])<2e-12 and abs(d['amplitude_product'][0])>2
                    np.savez_compressed(folder/'budget.npz',**d)
                    row=dict(label=name,identity_error=identity(d),budget=array_summary(d),budget_sha256=sha(folder/'budget.npz'))
                row['input_sha256']=sha(folder/'inputs.npz');report['cases'].append(row)
            window=covariance([1,3,7],13,cycle_samples=16,cycles=4,hop=4)
            np.savez_compressed(a.out/'small_window.npz',**window)
            report['small_window_sha256']=sha(a.out/'small_window.npz')
            report['result']='stereo_budget_known_controls_ready'
        else:
            known=load(consume(a.known/'report.json'));audit=load(consume(a.known_audit/'report.json'))
            assert known['result']=='stereo_budget_known_controls_ready' and known['sources']==report['sources']
            assert audit['result']=='independent_stereo_budget_audit_passed' and audit['producer_sha256']==sha(a.known/'report.json')
            parent=a.workspace/'baselines/relative_phase_v1'
            assert sha(consume(parent/'manifest.json'))==load(repo/'research/relative_phase_v1_summary.json')['manifest_sha256']
            entries={r['path']:r['sha256'] for r in load(parent/'manifest.json')['files']}
            def frozen(name):
                path=consume(parent/name);assert sha(path)==entries[name];return path
            prior=load(frozen('evidence/real1/report.json'));total_errors={'current':[],'population_gaussian':[]}
            regression_cases=[]
            for old in prior['cases']:
                label=old['label'];folder=a.out/label;folder.mkdir();root=old['root_hz']
                profile=dict(np.load(frozen(f'evidence/real1/{label}/profile.npz')))
                training=np.load(frozen(f'evidence/real1/{label}/training.npz'))
                q=training['source_rows'].reshape(-1,288,2,2);z=q[...,0]+1j*q[...,1]
                source=measure(abs(z),np.angle(z));source_moments=describe(abs(z),np.angle(z),root,plan['bands_Hz'])
                h=z.shape[1];hz=np.arange(1,h+1)*root
                groups=[np.flatnonzero((hz>=lo)&(hz<hi)) for lo,hi in plan['bands_Hz']]
                phase_integral=marginal_moment(profile['phase'][:,h:])
                # This is an exact population-covariance factor, not a tuned PCA rank.
                basis=training['scores'].T/np.sqrt(len(z))
                expected=training['scores'].T@training['scores']/len(z)
                covariance_error=float(abs(basis@basis.T-expected).max())
                assert covariance_error<plan['checks']['full_score_covariance_absolute']
                row=dict(label=label,root_hz=root,rows=len(z),QMC=[],population_score_covariance_error=covariance_error,
                         source=json_summary(source_moments))
                budgets=[];counterfactuals=[];fixed=[]
                for seed in plan['QMC']['seeds']:
                    original=np.load(frozen(f'evidence/real1/{label}/QMC_{seed}.npz'))
                    current=dict(product=original['budget_amplitude_product'],phase_moment=original['budget_relative_phase_moment'],
                        association=original['budget_amplitude_phase_association'])
                    current['cross']=current['product']*current['phase_moment']+current['association']
                    denominator=2*np.sqrt(original['relative_mean'].reshape(4,2).prod(axis=1))
                    d=decompose(source,current,groups,phase_integral,denominator)
                    assert abs(d['model_coherence']-original['relative_complex_coherence']).max()<2e-12
                    uniform=qmc.Sobol(d=len(z),scramble=True,seed=seed).random_base2(plan['QMC']['power'])
                    features=ndtri(uniform)@basis.T
                    A,P=decode(profile,features)
                    full=measure(A,P);cf=decompose(source,full,groups,phase_integral)
                    cf_moments=describe(A,P,root,plan['bands_Hz'])
                    path=folder/f'budget_{seed}.npz'
                    np.savez_compressed(path,**{'current_'+k:v for k,v in d.items()},
                        **{'population_'+k:v for k,v in cf.items()},
                        **{'population_stat_'+k:v for k,v in full.items()},
                        **{'population_moments_'+k:v for k,v in cf_moments.items()},
                        **{'source_'+k:v for k,v in source.items()},phase_integral=phase_integral)
                    row['QMC'].append(dict(seed=seed,sha256=sha(path),uniform_sha256=hashlib.sha256(uniform.tobytes()).hexdigest(),
                        current_identity_error=identity(d),population_identity_error=identity(cf),
                        current=array_summary(d),population=array_summary(cf)))
                    budgets.append(d);counterfactuals.append(cf)
                    fixed.append(original['fixed_complex_coherence'])
                mean_budget={k:np.mean([d[k] for d in budgets],axis=0) for k in budgets[0]}
                mean_cf={k:np.mean([d[k] for d in counterfactuals],axis=0) for k in counterfactuals[0]}
                fixed_error=abs(np.mean(fixed,axis=0)-mean_budget['source_coherence'])
                error=abs(mean_budget['error']);indices=np.flatnonzero(error>fixed_error)
                row.update(average=array_summary(mean_budget),population_average=array_summary(mean_cf),
                    fixed_error=fixed_error.tolist(),regressions_vs_fixed=indices.tolist())
                for band in indices:
                    e=mean_budget['error'][band];terms={k:mean_budget[k][band] for k in ['amplitude_product','phase_marginal','association','denominator']}
                    regression_cases.append(dict(label=label,band=int(band),error=float(abs(e)),fixed_error=float(fixed_error[band]),
                        signed_projection={k:float(np.real(v*e.conjugate())/abs(e)**2) for k,v in terms.items()},
                        absolute_terms={k:float(abs(v)) for k,v in terms.items()}))
                total_errors['current'].extend(error);total_errors['population_gaussian'].extend(abs(mean_cf['error']))
                power=source_moments['power'];temporal=observed(power)
                windows=[covariance(np.arange(1,h+1)[g],len(z)) for g in groups]
                arrays=dict(source_lag1_8=temporal)
                for j,w in enumerate(windows):arrays.update({f'band{j}_'+k:v for k,v in w.items()})
                np.savez_compressed(folder/'window.npz',**arrays)
                row['window']=dict(sha256=sha(folder/'window.npz'),source_lag1_8=temporal.tolist(),
                    population_lag1_8=[w['population_correlation'][1:9].tolist() for w in windows],
                    finite_demeaned_lag1_8=[w['finite_demeaned_correlation'][1:9].tolist() for w in windows])
                report['cases'].append(row);save(a.out/'report.json',report)
                print('PASS signed stereo budget and window null',label,flush=True)
            report['regression_cases']=regression_cases
            report['mean_coherence_error']={k:float(np.mean(v)) for k,v in total_errors.items()}
            report['population_counterfactual_improves_coordinates']=int(np.sum(np.array(total_errors['population_gaussian'])<total_errors['current']))
            report['diagnostic_not_preset']=True;report['runtime_or_timbre_changed']=False
            report['result']='six_source_stereo_budget_and_window_evidence_ready'
        save(a.out/'report.json',report);print(report['result'])
    except BaseException as exc:
        report.update(result='failed',error=repr(exc));save(a.out/'report.json',report);raise


if __name__=='__main__':main()

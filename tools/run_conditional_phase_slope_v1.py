"""Known controls and all source slope optimizations at frozen parent targets."""
import argparse
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load,save,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('workspace','out'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--stage',choices=['known','real'],required=True)
    p.add_argument('--known',type=Path);p.add_argument('--known-audit',type=Path)
    a=p.parse_args();repo=Path(__file__).resolve().parents[1]
    for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from conditional_phase_slope_v1.linear import optimize
    from conditional_phase_slope_v1.measure import measure,probes
    from conditional_phase_v1.transport import phase_cells
    a.out.mkdir(parents=True,exist_ok=False)
    report=dict(result='running',stage=a.stage,sources={},inputs={},cases=[])
    try:
        names=['research/conditional_phase_slope_v1_plan.json','tools/run_conditional_phase_slope_v1.py',
               'tools/conditional_phase_slope_v1/linear.py','tools/conditional_phase_slope_v1/measure.py',
               'tools/conditional_phase_v1/decoder.py','tools/conditional_phase_v1/transport.py']
        for name in names:
            path=a.out/'exact_sources'/name;path.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(repo/name,path);report['sources'][name]=sha(path)
        plan=load(repo/names[0]);tol=plan['LP']['primal_feasibility_tolerance'];gate=plan['checks']['scaled_primal_dual']
        def consume(path):report['inputs'][str(path)]=sha(path);return path

        def fit(folder,p,r,m,q,target,low,high,knots,parent_cdf):
            result=optimize(p,r,m,q,target,low,high,knots,.0001,tol,plan['moment_component_allowance'])
            folder.mkdir(parents=True,exist_ok=False)
            arrays=dict(product=p,row_mass=r,moments=m,column_mass=q,target=target,low=low,high=high,
                knots=knots,parent_cdf=parent_cdf,kappa=result['kappa'],kappa_required=result['kappa_required'],
                gradient_scale=result['gradient_scale'],moment_scales=result['moment_scales'],moment_active=result['moment_active'])
            row=dict(kappa=result['kappa'],kappa_required=result['kappa_required'],gradient_scale=result['gradient_scale'],stages={})
            for name,cdf in [('parent',parent_cdf)]+[(n,result[n]['cdf']) for n in ('density','variation')]:
                metrics=measure(cdf,knots,low,high);probe=probes(cdf,knots,low,high)
                cross=np.sum(r[:,None]*np.diff(cdf,axis=1)*p[:,None]*m[None,:])
                metrics.update(cross=[cross.real,cross.imag],cross_target_error=float(abs(cross-target)),
                    phase_marginal_error=float(abs(np.sum(r[:,None]*np.diff(cdf,axis=1),axis=0)-q).max()),
                    path_maximum_step_radians=probe['maximum_step_radians'],path_step_RMS_radians=probe['step_RMS_radians'])
                if name!='parent':
                    out=result[name]
                    assert max(abs(out[k]) for k in ['scaled_equality_error','scaled_inequality_error','stationarity_error',
                                                'primal_dual_gap'])<gate
                    # Physical error includes the declared moment interval AND
                    # measured scaled-solver/marginal residuals. A Euclidean
                    # 2e-9 cutoff incorrectly ignored that forward error.
                    scale=result['moment_scales']
                    marginal=(np.sum(r[:,None]*cdf[:,1:-1],axis=0)-np.cumsum(q)[:-1])
                    delta=m[:-1]-m[1:]
                    bounds=plan['moment_component_allowance']+scale*(out['scaled_inequality_error']+64*np.finfo(float).eps)
                    bounds+=abs(np.dot(p,r))*np.array([np.sum(abs(delta.real*marginal)),np.sum(abs(delta.imag*marginal))])
                    error=cross-target
                    assert np.all(np.array([abs(error.real),abs(error.imag)])<=bounds+2e-12)
                    metrics['moment_component_forward_bounds']=bounds.tolist()
                    assert metrics['cross_target_error']<plan['checks']['physical_marginal_and_cross']
                    assert metrics['phase_marginal_error']<plan['checks']['physical_marginal_and_cross']
                    metrics.update({k:v for k,v in out.items() if isinstance(v,float)})
                    arrays.update({name+'_'+k:v for k,v in out.items()})
                arrays.update({name+'_probe_'+k:v for k,v in probe.items()})
                row['stages'][name]=metrics
            np.savez_compressed(folder/'model.npz',**arrays);row['sha256']=sha(folder/'model.npz')
            return row

        if a.stage=='known':
            p=np.array([.5,1.5]);r=np.array([.5,.5]);knots=p.copy()
            table=np.array([-1.2,-.3,.4,1.2]);cells=phase_cells(table)
            q,m=cells['masses'],cells['moments'];w=r[:,None]*q[None,:]
            w[0,1]-=.025;w[1,3]-=.025;w[0,3]+=.025;w[1,1]+=.025
            associated=.9999*w+.0001*r[:,None]*q[None,:]
            cdf=np.column_stack([np.zeros(2),np.cumsum(associated/r[:,None],axis=1)])
            target=np.sum(p[:,None]*associated*m[None,:])
            fixtures=[('independent_linear_phase',p,r,phase_cells(np.array([-1.,1.])),None,None),
                ('associated_continuous_phase',p,r,cells,target,cdf),
                ('constant_product',np.ones(2),r,cells,None,None),
                ('single_row',np.array([1.]),np.array([1.]),cells,None,None),
                ('quarter_turn',p,r,dict(cells,low=cells['low']+np.pi/2,high=cells['high']+np.pi/2,moments=m*1j),target*1j,cdf),
                ('conjugate',p,r,dict(low=-cells['high'][::-1],high=-cells['low'][::-1],masses=q[::-1],moments=m[::-1].conj()),
                 target.conjugate(),1-cdf[:,::-1])]
            for label,pp,rr,cc,tt,old_cdf in fixtures:
                if tt is None:tt=np.dot(pp,rr)*np.dot(cc['masses'],cc['moments'])
                if old_cdf is None:old_cdf=np.tile(np.r_[0,np.cumsum(cc['masses'])],(len(pp),1))
                kk=np.linspace(.5,1.5,len(pp)) if len(pp)>1 else np.array([1.])
                row=fit(a.out/label,pp,rr,cc['moments'],cc['masses'],tt,cc['low'],cc['high'],kk,old_cdf)
                if label in ('independent_linear_phase','constant_product','single_row'):
                    width=cc['high']-cc['low'];expected=float(np.min(cc['masses'][width>0]/width[width>0]))
                    assert abs(row['kappa']-expected)<2e-7
                    assert row['stages']['variation']['cdf_product_gradient']<2e-7
                    row['expected_kappa']=expected
                report['cases'].append(dict(label=label,**row))
            fixed=phase_cells(np.full(4,.37))
            try:optimize(p,r,fixed['moments'],fixed['masses'],np.exp(.37j),fixed['low'],fixed['high'],knots,.0001,tol)
            except ValueError as exc:assert 'constant decoder' in str(exc)
            else:raise AssertionError('Fixed phase must use the exact constant decoder')
            report['cases'].append(dict(label='fixed_phase',exact_constant_decoder=True))
            try:optimize(p,r,m,q,2+2j,cells['low'],cells['high'],knots,.0001,tol)
            except RuntimeError:report['cases'].append(dict(label='invalid_target_rejected',rejected=True))
            else:raise AssertionError('Infeasible target accepted')
            report['result']='conditional_slope_known_controls_ready'
        else:
            known=load(consume(a.known/'report.json'));audit=load(consume(a.known_audit/'report.json'))
            assert known['result']=='conditional_slope_known_controls_ready'
            assert audit['result']=='independent_conditional_slope_audit_passed'
            assert audit['producer_sha256']==sha(a.known/'report.json') and known['sources']==report['sources']
            parent=a.workspace/'baselines/conditional_phase_feasibility_v1'
            manifest=load(consume(parent/'manifest.json'));assert sha(parent/'manifest.json')==load(repo/'research/conditional_phase_feasibility_v1_summary.json')['manifest_sha256']
            entries={x['path']:x['sha256'] for x in manifest['files']}
            def frozen(name):
                path=consume(parent/name);assert sha(path)==entries[name];return path
            prior=load(frozen('evidence/real1/report.json'))
            for old in prior['cases']:
                label=old['label'];folder=a.out/label;folder.mkdir()
                inputs=np.load(frozen(f'evidence/real1/{label}/inputs.npz'))
                target=[];row=dict(label=label,root_hz=old['root_hz'],harmonics=[])
                for h,previous in enumerate(old['harmonics']):
                    raw=np.load(frozen(f'evidence/real1/{label}/{h+1:03d}/transport.npz'))
                    t=complex(*previous['positive_cross']);target.append(t)
                    result=fit(folder/f'{h+1:03d}',raw['product'],raw['row_mass'],raw['phase_moments'],raw['phase_masses'],t,
                               raw['phase_low'],raw['phase_high'],raw['knots'],raw['cdf'])
                    result.update(order=h+1,mean_product=previous['mean_product'])
                    row['harmonics'].append(result)
                row['bands']=[];hz=np.arange(1,289)*old['root_hz']
                for band in old['bands']:
                    lo,hi=band['band_Hz'];mask=(hz>=lo)&(hz<hi);den=np.sqrt(inputs['energy'][mask].sum(axis=0).prod())
                    b=dict(band_Hz=[lo,hi],source=band['source'])
                    for stage in ('parent','density','variation'):
                        cross=sum(r['mean_product']*complex(*r['stages'][stage]['cross']) for r,yes in zip(row['harmonics'],mask) if yes)/den
                        b[stage]=[cross.real,cross.imag]
                    row['bands'].append(b)
                report['cases'].append(row);save(a.out/'report.json',report)
                print('PASS paired slope LPs288',label,flush=True)
            harmonics=[h for r in report['cases'] for h in r['harmonics']]
            report['summary']={}
            for key in ('inverse_uniform_slope_bound','inverse_product_slope_bound','cdf_product_gradient',
                        'path_maximum_step_radians','path_step_RMS_radians'):
                report['summary'][key]={stage:dict(quantiles=np.quantile([h['stages'][stage][key] for h in harmonics],
                    [0,.5,.9,.99,1]).tolist()) for stage in ('parent','density','variation')}
                report['summary'][key]['variation_improves_vs_parent']=sum(h['stages']['variation'][key]<h['stages']['parent'][key] for h in harmonics)
            report['result']='six_source_conditional_slope_evidence_ready'
        report['new_audio_or_runtime_adopted']=False;save(a.out/'report.json',report);print(report['result'],flush=True)
    except BaseException as exc:
        report.update(result='failed',error=repr(exc));save(a.out/'report.json',report);raise


if __name__=='__main__':main()

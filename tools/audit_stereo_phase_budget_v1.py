"""Independent cross-moment identities, phase integrals and Gaussian window null."""
import argparse
import hashlib
import math
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load,save,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('workspace','study','out'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();repo=Path(__file__).resolve().parents[1]
    for n in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[n]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from scipy import special
    from scipy.stats import qmc
    a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_audit.py')
    report=dict(result='running',cases=[],QMC_cases=0,max_phase_integral_error=0.,max_budget_error=0.,max_window_error=0.)
    try:
        producer=load(a.study/'report.json')
        assert producer['result'] in ('stereo_budget_known_controls_ready','six_source_stereo_budget_and_window_evidence_ready')
        for n,h in producer['sources'].items():assert sha(repo/n)==sha(a.study/'exact_sources'/n)==h
        for n,h in producer['inputs'].items():assert sha(n)==h
        plan=load(a.study/'exact_sources/research/stereo_phase_budget_v1_plan.json')
        def stats(A,P):
            angle=P[...,0]-P[...,1];U=np.cos(angle)+1j*np.sin(angle)
            product=A[...,0]*A[...,1];moment=U.mean(axis=0);p=product.mean(axis=0)
            cross=np.mean(product*U,axis=0)
            return dict(second=np.mean(A*A,axis=0),product=p,phase_moment=moment,cross=cross,association=cross-p*moment)
        def split(s,m,groups,integral=None,denominators=None):
            result={k:[] for k in ['source_coherence','model_coherence','error','amplitude_product','phase_marginal','association','denominator','phase_quantile_bias','phase_QMC_discrepancy']}
            for j,index in enumerate(groups):
                ds=math.sqrt(float(s['second'][index,0].sum()*s['second'][index,1].sum()))
                dm=math.sqrt(float(m['second'][index,0].sum()*m['second'][index,1].sum())) if denominators is None else denominators[j]
                assert ds>0 and dm>0
                cs=sum(s['cross'][index]);cm=sum(m['cross'][index]);terms=[]
                for h in index:
                    terms.append([(m['product'][h]-s['product'][h])*s['phase_moment'][h],
                        m['product'][h]*(m['phase_moment'][h]-s['phase_moment'][h]),m['association'][h]-s['association'][h]])
                t=np.sum(terms,axis=0)/ds
                bias=sum(m['product'][h]*(integral[h]-s['phase_moment'][h]) for h in index)/ds if integral is not None else t[1]
                for key,value in dict(source_coherence=cs/ds,model_coherence=cm/dm,error=cm/dm-cs/ds,
                    amplitude_product=t[0],phase_marginal=t[1],association=t[2],denominator=cm*(1/dm-1/ds),
                    phase_quantile_bias=bias,phase_QMC_discrepancy=t[1]-bias).items():result[key].append(value)
            return {k:np.array(v) for k,v in result.items()}
        def check_budget(saved,prefix,want,descriptor=None):
            for k,v in want.items():
                error=float(abs(saved[prefix+k]-v).max());assert error<2e-12
                report['max_budget_error']=max(report['max_budget_error'],error)
                if descriptor is not None:
                    value=np.array(descriptor[k]);assert abs(value[:,0]+1j*value[:,1]-v).max()<2e-12
            assert abs(want['error']-sum(want[k] for k in ['amplitude_product','phase_marginal','association','denominator'])).max()<2e-12
        def finite_window(orders,rows,size=4096,hop=256,cycles=4):
            def geometric(q,start):
                q=(q+size/2)%size-size/2;count=size-start
                output=np.full(q.shape,complex(count));active=q!=0
                output[active]=np.exp(-2j*np.pi*q[active]*(start+(count-1)/2)/size)*np.sin(np.pi*q[active]*count/size)/np.sin(np.pi*q[active]/size)
                return output
            def transform(k,start):
                phase=2*np.pi*start/size
                coeff={0:.25+.125*np.cos(phase),1:-.125*(1+np.exp(-1j*phase)),2:.0625*np.exp(-1j*phase)}
                coeff[-1]=np.conj(coeff[1]);coeff[-2]=np.conj(coeff[2])
                return sum(c*geometric(k-l,start) for l,c in coeff.items())
            k=np.array(orders)*cycles;lags=[]
            for lag in range(rows):
                shift=lag*hop
                if shift>=size:lags.append(0.);continue
                R=transform(k[:,None]-k[None,:],shift);P=transform(k[:,None]+k[None,:],shift)
                lags.append(float(4*np.sum(abs(R)**2+abs(P)**2)/(size/2)**4))
            lags=np.array(lags);matrix=lags[abs(np.arange(rows)[:,None]-np.arange(rows)[None,:])]
            H=np.eye(rows)-np.ones((rows,rows))/rows;centered=H@matrix@H
            population=lags/lags[0];finite=np.array([np.diag(centered,j).mean()/(np.trace(centered)/rows) for j in range(rows)])
            return lags,population,finite,centered
        if producer['stage']=='known':
            for row in producer['cases']:
                folder=a.study/row['label'];assert sha(folder/'inputs.npz')==row['input_sha256']
                data=np.load(folder/'inputs.npz');s=stats(data['source_amplitude'],data['source_phase']);m=stats(data['model_amplitude'],data['model_phase'])
                if row['label']=='silent_rejected':assert s['second'].sum()==0 and row['undefined_coherence_rejected']
                else:
                    path=folder/'budget.npz';assert sha(path)==row['budget_sha256'];d=split(s,m,[np.arange(1)])
                    check_budget(np.load(path),'',d,row['budget'])
                report['cases'].append(dict(label=row['label'],signed_identity_verified=True))
            path=a.study/'small_window.npz';assert sha(path)==producer['small_window_sha256'];saved=np.load(path)
            N=64;hop=4;rows=13;length=N+(rows-1)*hop;window=.5-.5*np.cos(2*np.pi*np.arange(N)/N)
            Q=[]
            for start in range(0,rows*hop,hop):
                op=np.zeros((length,length))
                for h in (1,3,7):
                    z=np.zeros(length,dtype=complex);times=np.arange(start,start+N)
                    z[times]=2*window/window.sum()*np.exp(-2j*np.pi*h*times/16)
                    op+=(np.outer(z.real,z.real)+np.outer(z.imag,z.imag))/2
                Q.append(op)
            dense=np.array([[2*np.sum(left*right) for right in Q] for left in Q])
            lags,population,finite,centered=finite_window([1,3,7],rows,N,hop)
            assert np.max(abs(dense-dense[0,abs(np.arange(rows)[:,None]-np.arange(rows)[None,:])]))<2e-13
            assert abs(dense[0]-saved['covariance_lags']).max()/dense[0,0]<2e-11
            assert abs(lags-saved['covariance_lags']).max()/lags[0]<2e-11
            H=np.eye(rows)-np.ones((rows,rows))/rows
            assert abs(H@dense@H-saved['finite_centered_covariance']).max()/dense[0,0]<2e-11
            assert abs(population-saved['population_correlation']).max()<2e-11
            assert abs(finite-saved['finite_demeaned_correlation']).max()<2e-11
            report['dense_real_quadratic_window_null_and_demeaning_verified']=True
        else:
            parent=a.workspace/'baselines/relative_phase_v1';old=load(parent/'evidence/real1/report.json')
            total_errors={'current':[],'population_gaussian':[]};regressions=[]
            nodes,weights=np.polynomial.legendre.leggauss(24)
            def inverse(table,normal):
                probability=.5+.5*special.erf(normal/math.sqrt(2));n=len(table)
                x=np.r_[0,(np.arange(n)+.5)/n,1]
                return np.column_stack([np.interp(probability[:,j],x,np.r_[table[0,j],table[:,j],table[-1,j]]) for j in range(table.shape[1])])
            for row in producer['cases']:
                folder=a.study/row['label'];original=next(v for v in old['cases'] if v['label']==row['label'])
                model=dict(np.load(parent/f'evidence/real1/{row["label"]}/profile.npz'))
                training=np.load(parent/f'evidence/real1/{row["label"]}/training.npz')
                raw=training['source_rows'].reshape(-1,288,2,2);z=raw[...,0]+1j*raw[...,1];s=stats(abs(z),np.angle(z))
                h=z.shape[1];table=model['phase'][:,h:];n=len(table)
                phase_integral=(np.exp(1j*table[0])+np.exp(1j*table[-1]))/(2*n)
                for i in range(n-1):
                    val=table[i,None,:]+(nodes[:,None]+1)/2*(table[i+1]-table[i])[None,:]
                    phase_integral+=np.sum(weights[:,None]*np.exp(1j*val),axis=0)/(2*n)
                indices=[np.flatnonzero((np.arange(1,h+1)*row['root_hz']>=lo)&(np.arange(1,h+1)*row['root_hz']<hi)) for lo,hi in plan['bands_Hz']]
                original_budgets=[];population_budgets=[];fixed=[]
                for q in row['QMC']:
                    path=folder/f'budget_{q["seed"]}.npz';assert sha(path)==q['sha256'];saved=np.load(path)
                    e=float(abs(phase_integral-saved['phase_integral']).max());assert e<2e-12;report['max_phase_integral_error']=max(report['max_phase_integral_error'],e)
                    previous=np.load(parent/f'evidence/real1/{row["label"]}/QMC_{q["seed"]}.npz')
                    current=dict(product=previous['budget_amplitude_product'],phase_moment=previous['budget_relative_phase_moment'],association=previous['budget_amplitude_phase_association'])
                    current['cross']=current['product']*current['phase_moment']+current['association']
                    denominator=2*np.sqrt(previous['relative_mean'].reshape(4,2).prod(axis=1))
                    d=split(s,current,indices,phase_integral,denominator);check_budget(saved,'current_',d,q['current']);original_budgets.append(d)
                    uniform=qmc.Sobol(d=len(z),scramble=True,seed=q['seed']).random_base2(plan['QMC']['power'])
                    assert hashlib.sha256(uniform.tobytes()).hexdigest()==q['uniform_sha256']
                    normal=math.sqrt(2)*special.erfinv(2*uniform-1)
                    features=np.einsum('nk,kd->nd',normal,training['scores'],optimize=False)/math.sqrt(len(z))
                    A=inverse(model['amplitude'],features[:,:2*h]).reshape(len(features),h,2)
                    coordinates=inverse(model['phase'],features[:,2*h:])
                    P=np.stack([coordinates[:,:h]+coordinates[:,h:]/2,coordinates[:,:h]-coordinates[:,h:]/2],axis=-1)
                    measured=stats(A,P);cf=split(s,measured,indices,phase_integral);check_budget(saved,'population_',cf,q['population']);population_budgets.append(cf)
                    for k,v in measured.items():assert abs(v-saved['population_stat_'+k]).max()<2e-12
                    power=np.array([np.sum(A[:,g,c]**2,axis=1)/2 for g in indices for c in (0,1)]).T
                    mean=power.mean(axis=0);cov=np.cov(power,rowvar=False,ddof=0)
                    assert (abs(power-saved['population_moments_power'])/mean).max()<2e-10
                    assert (abs(cov-saved['population_moments_covariance'])/np.outer(mean,mean)).max()<2e-10
                    assert abs(cf['model_coherence']-saved['population_moments_complex_coherence']).max()<2e-12
                    fixed.append(previous['fixed_complex_coherence']);report['QMC_cases']+=1
                mean={k:np.mean([v[k] for v in original_budgets],axis=0) for k in original_budgets[0]}
                full={k:np.mean([v[k] for v in population_budgets],axis=0) for k in population_budgets[0]}
                for descriptor,values in [(row['average'],mean),(row['population_average'],full)]:
                    for k,v in values.items():
                        actual=np.array(descriptor[k]);assert abs(actual[:,0]+1j*actual[:,1]-v).max()<2e-12
                fixed_error=abs(np.mean(fixed,axis=0)-mean['source_coherence']);error=abs(mean['error'])
                assert np.array_equal(np.flatnonzero(error>fixed_error),row['regressions_vs_fixed'])
                total_errors['current'].extend(error);total_errors['population_gaussian'].extend(abs(full['error']))
                for band in row['regressions_vs_fixed']:
                    item=next(v for v in producer['regression_cases'] if v['label']==row['label'] and v['band']==band)
                    for key in ('amplitude_product','phase_marginal','association','denominator'):
                        actual=float(np.real(mean[key][band]*mean['error'][band].conjugate())/abs(mean['error'][band])**2)
                        assert abs(actual-item['signed_projection'][key])<2e-10
                        assert abs(abs(mean[key][band])-item['absolute_terms'][key])<2e-12
                    assert abs(abs(mean['error'][band])-item['error'])<2e-12
                    assert abs(fixed_error[band]-item['fixed_error'])<2e-12
                path=folder/'window.npz';assert sha(path)==row['window']['sha256'];window_saved=np.load(path)
                power=np.array([np.sum(abs(z[:,g,c])**2,axis=1)/2 for g in indices for c in (0,1)]).T
                centered=power-power.mean(axis=0);variance=np.mean(centered**2,axis=0)
                observed=np.array([np.einsum('ni,ni->i',centered[:-k],centered[k:],optimize=False)/(len(power)-k)/variance for k in range(1,9)])
                assert abs(observed-window_saved['source_lag1_8']).max()<2e-12
                assert abs(observed-np.asarray(row['window']['source_lag1_8'])).max()<2e-12
                source_mean=power.mean(axis=0);source_cov=np.cov(power,rowvar=False,ddof=0)
                assert abs(source_mean/row['source']['mean']-1).max()<2e-12
                assert (abs(source_cov-row['source']['covariance'])/np.outer(source_mean,source_mean)).max()<2e-10
                for j,index in enumerate(indices):
                    lags,population,finite,centered=finite_window(index+1,len(z))
                    e=max(float(abs(population-window_saved[f'band{j}_population_correlation']).max()),float(abs(finite-window_saved[f'band{j}_finite_demeaned_correlation']).max()))
                    assert e<2e-11;report['max_window_error']=max(report['max_window_error'],e)
                    assert abs(population[1:9]-row['window']['population_lag1_8'][j]).max()<2e-11
                    assert abs(finite[1:9]-row['window']['finite_demeaned_lag1_8'][j]).max()<2e-11
                report['cases'].append(dict(label=row['label'],full_signed_budgets_phase_quadrature_and_window_null_verified=True))
            for key,values in total_errors.items():assert abs(np.mean(values)-producer['mean_coherence_error'][key])<2e-12
            assert int(np.sum(np.array(total_errors['population_gaussian'])<total_errors['current']))==producer['population_counterfactual_improves_coordinates']
            report['all_report_aggregates_independently_verified']=True
        report.update(result='independent_stereo_budget_audit_passed',producer_sha256=sha(a.study/'report.json'),auditor_sha256=sha(a.out/'executed_audit.py'))
        save(a.out/'report.json',report);print(report['result'])
    except BaseException as exc:
        report.update(result='failed',error=repr(exc));save(a.out/'report.json',report);raise


if __name__=='__main__':main()

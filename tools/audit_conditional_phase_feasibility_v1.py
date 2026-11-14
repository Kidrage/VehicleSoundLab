"""Independent hats, phase quadrature, transport duality and inverse-CDF audit."""
import argparse
import hashlib
import math
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load, save, sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('workspace','study','out'):
        p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();repo=Path(__file__).resolve().parents[1]
    for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
        os.environ[name]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from scipy.special import erf,ndtri
    from scipy.stats import qmc
    a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_audit.py')
    report=dict(result='running',harmonics=0,cases=[],maximum_primal_dual_error=0.,
                maximum_phase_quadrature_error=0.,maximum_decoder_error=0.,maximum_amplitude_normalized_error=0.)
    try:
        producer=load(a.study/'report.json');assert producer['result'] in (
            'conditional_phase_known_controls_ready','six_source_conditional_phase_feasibility_ready')
        for n,h in producer['sources'].items():assert sha(repo/n)==sha(a.study/'exact_sources'/n)==h
        for n,h in producer['inputs'].items():assert sha(n)==h
        plan=load(a.study/'exact_sources/research/conditional_phase_feasibility_v1_plan.json')
        gate=plan['checks']['primal_dual_normalized'];floor=plan['positivity_probe']
        nodes,weights=np.polynomial.legendre.leggauss(16)

        def basis(values,knots):
            if len(knots)==1:return np.ones((len(values),1))
            columns=[]
            for i,x in enumerate(knots):
                if i==0:value=np.clip((knots[1]-values)/(knots[1]-x),0,1)
                elif i==len(knots)-1:value=np.clip((values-knots[i-1])/(x-knots[i-1]),0,1)
                else:value=np.minimum(np.clip((values-knots[i-1])/(x-knots[i-1]),0,1),
                                      np.clip((knots[i+1]-values)/(knots[i+1]-x),0,1))
                columns.append(value)
            return np.column_stack(columns)

        def inverse(product,uniform,knots,cdf,low,high):
            result=[]
            for x,u in zip(product,uniform):
                probs=basis(np.array([x]),knots)[0]@np.diff(cdf,axis=1)
                boundaries=np.r_[0,np.cumsum(probs)];boundaries[-1]=1
                j=next((i for i in range(len(probs)) if u<boundaries[i+1]),len(probs)-1)
                result.append(low[j]+(high[j]-low[j])*(u-boundaries[j])/(boundaries[j+1]-boundaries[j]))
            return np.array(result)

        def atomic_optimum(product,r,m,q,target):
            if len(product)==1 or len(m)==1:
                error=np.dot(product,r)*np.dot(m,q)-target
                return max(abs(error.real),abs(error.imag))
            assert len(product)==len(m)==2
            lo=max(0,r[0]+q[0]-1);hi=min(r[0],q[0])
            def moment(t):
                w=np.array([[t,r[0]-t],[q[0]-t,1-r[0]-q[0]+t]])
                return np.sum(w*product[:,None]*m[None,:])
            first=moment(0)-target;slope=moment(1)-moment(0)
            intercept=np.array([first.real,-first.real,first.imag,-first.imag])
            gradient=np.array([slope.real,-slope.real,slope.imag,-slope.imag])
            candidates=[lo,hi]
            for i in range(4):
                for j in range(i):
                    if gradient[i]!=gradient[j]:
                        t=(intercept[j]-intercept[i])/(gradient[i]-gradient[j])
                        if lo<=t<=hi:candidates.append(t)
            return min(float(np.max(intercept+t*gradient)) for t in candidates)

        def audit_transport(path,row,product_draws=None,table=None):
            assert sha(path)==row['sha256'];z=np.load(path)
            p,r=z['product'],z['row_mass'];q=z['phase_masses'];w=z['coupling']
            low,high=z['phase_low'],z['phase_high'];target=complex(z['target'])
            m=np.sum(np.exp(1j*((low+high)[:,None]/2+(high-low)[:,None]*nodes/2))*weights,axis=1)/2
            phase_error=float(abs(m-z['phase_moments']).max());assert phase_error<2e-12
            report['maximum_phase_quadrature_error']=max(report['maximum_phase_quadrature_error'],phase_error)
            if table is not None:
                n=len(table)
                assert np.array_equal(low,np.r_[table[0],table[:-1],table[-1]])
                assert np.array_equal(high,np.r_[table[0],table[1:],table[-1]])
                assert np.array_equal(q,np.r_[.5,np.ones(n-1),.5]/n)
            if product_draws is not None:
                mean=product_draws.mean();normal=product_draws/mean;sorted_values=np.sort(normal)
                position=np.linspace(0,len(normal)-1,plan['hat_knots'])
                i=np.floor(position).astype(int);u=position-i
                expected=np.unique((1-u)*sorted_values[i]+u*sorted_values[np.minimum(i+1,len(normal)-1)])
                assert abs(expected-z['knots']).max()<2e-12
                b=basis(normal,z['knots']);rr=np.sum(b,axis=0)/len(normal)
                pp=(b.T@normal)/len(normal)/rr
                assert abs(b.sum(axis=1)-1).max()<2e-12
                assert max(abs(rr-r).max(),abs(pp-p).max(),abs(np.dot(p,r)-1))<2e-12
                assert abs(mean-row['mean_product'])<mean*2e-12
            actual=np.sum(w*p[:,None]*m[None,:]);tau=float(z['tau'])
            yr=z['equality_dual'][:len(r)];yc=np.r_[z['equality_dual'][len(r):],0]
            lam=z['inequality_dual'];dual=z['lower_dual']
            direction=(lam[0]-lam[1])*m.real+(lam[2]-lam[3])*m.imag
            reduced_w=-yr[:,None]-yc[None,:]-p[:,None]*direction[None,:]
            reduced_tau=1+sum(lam)
            dual_objective=np.dot(r,yr)+np.dot(q,yc)+(lam[0]-lam[1])*target.real+(lam[2]-lam[3])*target.imag
            residuals=[abs(w.sum(axis=1)-r).max(),abs(w.sum(axis=0)-q).max(),
                       max(0,-w.min(),-tau),max(0,lam.max(),-dual.min()),
                       abs(reduced_w.ravel()-dual[:-1]).max(),abs(reduced_tau-dual[-1]),
                       abs(tau-dual_objective),abs(row['tau']-tau),
                       max(0,abs((actual-target).real)-tau,abs((actual-target).imag)-tau),
                       abs(actual-complex(*row['optimum_cross']))]
            error=float(max(residuals));assert error<gate,(path,error)
            report['maximum_primal_dual_error']=max(report['maximum_primal_dual_error'],error)
            joint=(1-floor)*w+floor*r[:,None]*q[None,:]
            conditional=joint/r[:,None];cdf=np.column_stack([np.zeros(len(r)),np.cumsum(conditional,axis=1)])
            assert abs(cdf-z['cdf']).max()<2e-12 and np.min(conditional)>0
            positive=np.sum(joint*p[:,None]*m[None,:])
            assert abs(positive-complex(*row['positive_cross']))<2e-12
            assert abs(abs(positive-target)-row['positive_error'])<2e-12
            independent=np.dot(r,p)*np.dot(q,m)
            assert abs(independent-complex(*row['independent_cross']))<2e-12
            # The deployed representation is a cumulative table. Its literal
            # adjacent differences differ from ideal joint/r probabilities by
            # ~1ULP, amplified by tiny cells. Verify that conversion separately
            # and audit the slope of the actual table, without relaxing gates.
            table_probability=np.array([[cdf[i,j+1]-cdf[i,j] for j in range(len(q))] for i in range(len(r))])
            assert abs(table_probability-conditional).max()<64*np.finfo(float).eps
            slope=float(np.max((high-low)[None,:]/table_probability))
            assert abs(slope-row['inverse_uniform_slope_bound'])<max(1e-12,abs(slope)*2e-12)
            cdf_difference=np.diff(cdf,axis=0)
            if len(r)>1:
                bound=((high-low)[None,:]/np.minimum(table_probability[:-1],table_probability[1:])*
                    np.maximum(abs(cdf_difference[:,:-1]),abs(cdf_difference[:,1:]))/np.diff(z['knots'])[:,None])
                product_slope=float(np.max(bound))
            else:product_slope=0.
            assert abs(product_slope-row['inverse_product_slope_bound'])<max(1e-10,abs(product_slope)*2e-12)
            decoded=inverse(z['probe_product'],z['probe_uniform'],z['knots'],cdf,low,high)
            decoder_error=float(abs(decoded-z['probe_phase']).max());assert decoder_error<2e-9
            report['maximum_decoder_error']=max(report['maximum_decoder_error'],decoder_error)
            report['harmonics']+=1
            return actual,positive

        if producer['stage']=='known':
            for row in producer['cases']:
                if row['label']=='silent_rejected':assert row['rejected'];continue
                path=a.study/row['label']/'transport.npz';audit_transport(path,row)
                z=np.load(path);expected=atomic_optimum(z['product'],z['row_mass'],z['phase_moments'],z['phase_masses'],complex(z['target']))
                assert abs(expected-row['tau'])<2e-9 and abs(expected-row['expected_tau'])<2e-9
                report['cases'].append(dict(label=row['label'],enumerated_optimum=expected))
            path=a.study/'continuous_control.npz';assert sha(path)==producer['continuous_control_sha256'];z=np.load(path)
            x=z['probe_product'];u=z['probe_uniform'];kwargs=[z['knots'],z['cdf'],z['phase_low'],z['phase_high']]
            diff=float(abs(inverse(x+1e-10,u,*kwargs)-inverse(x-1e-10,u,*kwargs)).max())
            assert diff<1e-5 and abs(diff-float(z['maximum_difference']))<2e-12
            report['known_controls_and_continuity_verified']=True
        else:
            errors={key:[] for key in ['parent_pooled','LP_class','positive_probe']}
            count_inexact=0;count_universal=0;uniform_slopes=[];product_slopes=[]
            frozen=a.workspace/'baselines/relative_phase_v1/evidence/real1'
            original=load(frozen/'report.json');original_cases={r['label']:r for r in original['cases']}
            for row in producer['cases']:
                folder=a.study/row['label'];path=folder/'inputs.npz';assert sha(path)==row['input_sha256'];inputs=np.load(path)
                profile=np.load(frozen/row['label']/'profile.npz');training=np.load(frozen/row['label']/'training.npz')
                products=[];energies=[]
                for qrow in row['original_QMC_uniform_hashes']:
                    uniform=qmc.Sobol(d=1164,scramble=True,seed=qrow['seed']).random_base2(plan['QMC']['power'])
                    assert hashlib.sha256(uniform.tobytes()).hexdigest()==qrow['sha256']
                    normal=ndtri(uniform)
                    feature=np.einsum('nk,dk->nd',normal[:,:12],profile['basis'][:576],optimize=False)
                    feature+=normal[:,12:588]*profile['residual_std'][:576]
                    probability=(1+erf(feature/math.sqrt(2)))/2
                    n=len(profile['amplitude']);positions=np.r_[0,(np.arange(n)+.5)/n,1]
                    amp=np.column_stack([np.interp(probability[:,j],positions,
                        np.r_[profile['amplitude'][0,j],profile['amplitude'][:,j],profile['amplitude'][-1,j]]) for j in range(576)]).reshape(-1,288,2)
                    products.append(amp[:,:,0]*amp[:,:,1]);energies.append(np.mean(amp**2,axis=0))
                expected=np.concatenate(products);normalized=float(np.max(abs(expected-inputs['product'])/inputs['product'].mean(axis=0)))
                assert normalized<2e-11;report['maximum_amplitude_normalized_error']=max(report['maximum_amplitude_normalized_error'],normalized)
                assert np.max(abs(np.mean(energies,axis=0)/inputs['energy']-1))<2e-11
                raw=training['source_rows'].reshape(-1,288,2,2);source=raw[...,0]+1j*raw[...,1]
                target=np.sum(source[:,:,0]*source[:,:,1].conj(),axis=0)/len(source)
                assert abs(target-inputs['target']).max()<2e-12
                opt=[];pos=[]
                for h,r in enumerate(row['harmonics']):
                    actual,positive=audit_transport(folder/f'{h+1:03d}'/'transport.npz',r,inputs['product'][:,h],profile['phase'][:,288+h])
                    mean=inputs['product'][:,h].mean();assert r['order']==h+1
                    assert abs(r['independent_phase_universal_gap']-max(0,abs(target[h])/mean-1))<2e-12
                    count_inexact+=r['tau']>gate;count_universal+=r['independent_phase_universal_gap']>gate
                    uniform_slopes.append(r['inverse_uniform_slope_bound']);product_slopes.append(r['inverse_product_slope_bound'])
                    opt.append(actual*mean);pos.append(positive*mean)
                hz=np.arange(1,289)*row['root_hz']
                assert row['root_hz']==original_cases[row['label']]['root_hz']
                for b in row['bands']:
                    lo,hi=b['band_Hz'];mask=(hz>=lo)&(hz<hi)
                    denominator=math.sqrt(np.prod(inputs['energy'][mask].sum(axis=0)))
                    ds=math.sqrt(np.prod(inputs['source_energy'][mask].sum(axis=0)))
                    ref=target[mask].sum()/ds;assert abs(ref-complex(*b['source']))<2e-12
                    for key,values in [('parent_pooled',inputs['baseline']),('LP_class',np.array(opt)),('positive_probe',np.array(pos))]:
                        value=values[mask].sum()/denominator
                        assert abs(value-complex(*b[key]))<2e-12;errors[key].append(float(abs(value-ref)))
                report['cases'].append(dict(label=row['label'],harmonics=288))
                print('PASS independent288 LP/cdf/amplitude audit',row['label'],flush=True)
            assert count_inexact==producer['class_inexact_harmonics']
            assert count_universal==producer['universal_finite_amplitude_gap_harmonics']
            assert max(uniform_slopes)==producer['maximum_inverse_uniform_slope_bound']
            assert max(product_slopes)==producer['maximum_inverse_product_slope_bound']
            for key,values in errors.items():
                assert np.max(abs(np.array(values)-producer['band_complex_errors'][key]))<2e-12
                assert abs(float(np.mean(values))-producer['mean_band_complex_error'][key])<2e-12
            report['all_aggregates_independently_verified']=True
        report.update(result='independent_conditional_phase_audit_passed',producer_sha256=sha(a.study/'report.json'),auditor_sha256=sha(__file__))
        save(a.out/'report.json',report);print(report['result'],flush=True)
    except BaseException as exc:
        report.update(result='failed',error=repr(exc));save(a.out/'report.json',report);raise


if __name__=='__main__':main()

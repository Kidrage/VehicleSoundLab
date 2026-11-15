"""Independent CDF calculus, full LP duality, quadrature and path checks."""
import argparse
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load,save,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('workspace','study','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();repo=Path(__file__).resolve().parents[1]
    for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from fractions import Fraction
    a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_audit.py')
    report=dict(result='running',models=0,LP_certificates=0,cases=[],maximum_scaled_certificate_error=0.,
                maximum_physical_moment_error=0.,maximum_path_error_radians=0.,maximum_phase_integral_error=0.)
    try:
        producer=load(a.study/'report.json');assert producer['result'] in ('conditional_slope_known_controls_ready','six_source_conditional_slope_evidence_ready')
        for n,h in producer['sources'].items():assert sha(repo/n)==sha(a.study/'exact_sources'/n)==h
        for n,h in producer['inputs'].items():assert sha(n)==h
        plan=load(a.study/'exact_sources/research/conditional_phase_slope_v1_plan.json')
        gate=plan['checks']['scaled_primal_dual'];nodes,weights=np.polynomial.legendre.leggauss(20)
        def metrics(cdf,knots,low,high):
            prob=cdf[:,1:]-cdf[:,:-1];width=high-low
            assert prob.min()>0
            lu=float((width[None,:]/prob).max())
            if len(knots)>1:
                d=(cdf[1:]-cdf[:-1])/np.diff(knots)[:,None]
                g=float(abs(d).max())
                lp=float((width[None,:]*np.maximum(abs(d[:,:-1]),abs(d[:,1:]))/
                    np.minimum(prob[1:],prob[:-1])).max())
            else:g=lp=0.
            return dict(inverse_uniform_slope_bound=lu,cdf_product_gradient=g,inverse_product_slope_bound=lp,
                        minimum_cell_probability=float(prob.min()))

        def path(cdf,knots,low,high,product,uniform):
            cumulative=np.column_stack([np.interp(product,knots,cdf[:,j]) for j in range(cdf.shape[1])])
            cumulative[:,0]=0;cumulative[:,-1]=1
            right=np.sum(cumulative<=uniform[:,None],axis=1);right=np.clip(right,1,len(low))
            left=right-1;index=np.arange(len(product))
            fraction=(uniform-cumulative[index,left])/(cumulative[index,right]-cumulative[index,left])
            return low[left]+fraction*(high[left]-low[left])

        def check(pathname,row,parent=None):
            assert sha(pathname)==row['sha256'];z=np.load(pathname)
            p,r,q=z['product'],z['row_mass'],z['column_mass'];low,high=z['low'],z['high'];knots=z['knots']
            target=complex(z['target']);rows=len(r);J=len(q);n=rows*(J-1)
            m=(np.exp(1j*((low+high)[:,None]/2+(high-low)[:,None]*nodes/2))*weights).sum(axis=1)/2
            err=float(abs(m-z['moments']).max());assert err<2e-12
            report['maximum_phase_integral_error']=max(report['maximum_phase_integral_error'],err)
            if parent is not None:
                old,previous=parent
                for name,before in [('product','product'),('row_mass','row_mass'),('column_mass','phase_masses'),
                                    ('low','phase_low'),('high','phase_high'),('knots','knots'),('parent_cdf','cdf')]:
                    assert np.array_equal(z[name],old[before]),name
                assert abs(target-complex(*previous['positive_cross']))<2e-12
            mean=np.dot(p,r);center=(p-mean)*r
            coefficient=center[:,None]*(m[:-1]-m[1:])[None,:]
            residual=target-mean*np.dot(q,m)-center.sum()*m[-1]
            components=[coefficient.real,coefficient.imag];goals=[residual.real,residual.imag]
            scales=np.array([np.sum(abs(v)) for v in components]);active=scales!=0
            assert np.array_equal(active,z['moment_active'])
            assert np.max(abs(scales-z['moment_scales']))<2e-12
            # Use the exact declared coefficient data for the target's stored LP
            # certificate, after independent Gauss quadrature checks its meaning.
            mm=z['moments'];coeff=center[:,None]*(mm[:-1]-mm[1:])[None,:]
            res=target-mean*np.dot(q,mm)-center.sum()*mm[-1]
            comp=[coeff.real,coeff.imag];goal=[res.real,res.imag]
            scale=np.array([np.sum(abs(v)) for v in comp])
            expected_required=max(0,float(z['kappa'])-max(2e-10,abs(float(z['kappa']))*1e-8))
            assert abs(expected_required-float(z['kappa_required']))<2e-12
            for stage in ('density','variation'):
                x=z[stage+'_x'];cdf=z[stage+'_cdf'];prob=np.diff(cdf,axis=1)
                assert np.array_equal(cdf[:,1:-1].ravel(),x[:-1])
                assert np.array_equal(cdf[:,0],np.zeros(rows)) and np.array_equal(cdf[:,-1],np.ones(rows))
                eq_rhs=list(np.cumsum(q)[:-1]);eq_value=list(np.sum(r[:,None]*cdf[:,1:-1],axis=0))
                eq_gradient=np.tile(r[:,None],(1,J-1))*z[stage+'_equality_dual'][:J-1][None,:]
                y=z[stage+'_equality_dual'];assert len(y)==J-1
                full_lam=z[stage+'_inequality_dual'];count=int(np.sum(scale!=0))
                lam=full_lam[:-2*count] if count else full_lam
                ub_grad=np.zeros((rows,J-1));last_grad=0.;ub_rhs=[];ub_violation=[]
                if stage=='density':
                    lower=np.tile(.0001*q,(rows,1));first=lam[:rows*J].reshape(rows,J)
                    second=lam[rows*J:].reshape(rows,J)
                    assert len(lam)==2*rows*J
                    ub_grad+=-first[:,:-1]+first[:,1:]-second[:,:-1]+second[:,1:]
                    last_grad=float(np.sum(second*(high-low)[None,:]))
                    end=np.tile(np.r_[np.zeros(J-1),1.],(rows,1))
                    ub_rhs=list((end-lower).ravel())+list(end.ravel())
                    ub_violation=[float(np.max(lower-prob)),float(np.max(x[-1]*(high-low)[None,:]-prob))]
                    objective=-float(x[-1]);c_last=-1.;upper_last=0.
                    assert abs(x[-1]-z['kappa'])<2e-12
                else:
                    lower=np.tile(np.maximum(.0001*q,float(z['kappa_required'])*(high-low)),(rows,1))
                    first=lam[:rows*J].reshape(rows,J);ub_grad+=-first[:,:-1]+first[:,1:]
                    end=np.tile(np.r_[np.zeros(J-1),1.],(rows,1));ub_rhs=list((end-lower).ravel())
                    ub_violation=[float(np.max(lower-prob))];li=rows*J
                    for i,gap in enumerate(np.diff(knots)):
                        denominator=max(1,float(z['gradient_scale'])*gap)
                        for j in range(J-1):
                            for sign in (1.,-1.):
                                v=lam[li];li+=1
                                ub_grad[i,j]-=sign*v/denominator;ub_grad[i+1,j]+=sign*v/denominator
                                last_grad-=float(z['gradient_scale'])*gap*v/denominator;ub_rhs.append(0.)
                                ub_violation.append((sign*(cdf[i+1,j+1]-cdf[i,j+1])-float(z['gradient_scale'])*gap*x[-1])/denominator)
                    assert li==len(lam);objective=float(x[-1]);c_last=1.;upper_last=float(z[stage+'_upper_dual'][-1])
                if count:
                    positive=full_lam[-2*count:-count];negative=full_lam[-count:]
                    selected=[(component,g,s) for component,g,s in zip(comp,goal,scale) if s]
                    allowance=plan['moment_component_allowance']
                    for i,(component,g,s) in enumerate(selected):
                        ub_grad+=component/s*(positive[i]-negative[i])
                        ub_violation.append((abs(np.sum(component*cdf[:,1:-1])-g)-allowance)/s)
                    ub_rhs.extend([(g+allowance)/s for component,g,s in selected])
                    ub_rhs.extend([(-g+allowance)/s for component,g,s in selected])
                reduced=np.r_[(-eq_gradient-ub_grad).ravel(),c_last-last_grad]
                lower_dual=z[stage+'_lower_dual'];upper_dual=z[stage+'_upper_dual']
                # Exact binary-rational products/sum independently check the
                # offline producer's decimal accumulation. The original gate
                # remains unchanged, including the sign of the gap.
                exact_dual=sum((Fraction(float(v))*Fraction(float(w)) for v,w in zip(eq_rhs,y)),Fraction())
                exact_dual+=sum((Fraction(float(v))*Fraction(float(w)) for v,w in zip(ub_rhs,full_lam)),Fraction())
                exact_dual+=sum((Fraction(float(v)) for v in upper_dual[:-1]),Fraction())+Fraction(float(upper_last))
                gap=float(Fraction(float(objective))-exact_dual)
                errors=[max(0,-x.min(),np.max(x[:-1]-1)),max(0,float(full_lam.max()),-float(lower_dual.min()),float(upper_dual.max())),
                    abs(reduced-lower_dual-upper_dual).max(),abs(gap),
                    abs(np.array(eq_value)-eq_rhs).max(),max(0,max(ub_violation)),
                    abs(objective-row['stages'][stage]['objective'])]
                if stage=='variation':errors.append(max(0,x[-1]-1))
                error=float(max(errors));assert error<gate,(pathname,stage,error)
                report['maximum_scaled_certificate_error']=max(report['maximum_scaled_certificate_error'],error)
                cross=np.sum(r[:,None]*prob*p[:,None]*m[None,:]);physical=max(abs(cross-target),abs(np.sum(r[:,None]*prob,axis=0)-q).max())
                assert physical<2e-7;report['maximum_physical_moment_error']=max(report['maximum_physical_moment_error'],float(physical))
                marginal=np.sum(r[:,None]*cdf[:,1:-1],axis=0)-np.cumsum(q)[:-1]
                delta=mm[:-1]-mm[1:];numerical=max(0,max(ub_violation))
                forward=plan['moment_component_allowance']+scale*(numerical+64*np.finfo(float).eps)
                forward+=abs(mean)*np.array([np.sum(abs(delta.real*marginal)),np.sum(abs(delta.imag*marginal))])
                assert abs(forward-row['stages'][stage]['moment_component_forward_bounds']).max()<2e-10
                assert max(abs((cross-target).real)-forward[0],abs((cross-target).imag)-forward[1])<2e-12
                report['LP_certificates']+=1
            for stage in ('parent','density','variation'):
                cdf=z['parent_cdf'] if stage=='parent' else z[stage+'_cdf'];expected=metrics(cdf,knots,low,high)
                for key,value in expected.items():
                    assert abs(value-row['stages'][stage][key])<max(2e-10,abs(value)*2e-12),(key,value)
                xx=z[stage+'_probe_product'];uu=z[stage+'_probe_uniform']
                # Independently bind the saved inputs to the declared 1025-point
                # paths, rather than only accepting internally consistent phases.
                time=np.arange(1025,dtype=float)/1024
                expected_product=(knots[0]+knots[-1])/2-.45*(knots[-1]-knots[0])*np.cos(2*np.pi*time)
                expected_uniform=.5+.45*np.sin(4*np.pi*time+.31)
                assert xx.shape==uu.shape==(1025,)
                assert abs(xx-expected_product).max()<64*np.finfo(float).eps*max(1.,abs(knots).max())
                assert abs(uu-expected_uniform).max()<64*np.finfo(float).eps
                assert np.array_equal(xx,z['parent_probe_product']) and np.array_equal(uu,z['parent_probe_uniform'])
                phase=path(cdf,knots,low,high,xx,uu)
                path_error=float(abs(phase-z[stage+'_probe_phase']).max());assert path_error<2e-8
                report['maximum_path_error_radians']=max(report['maximum_path_error_radians'],path_error)
                steps=np.diff(phase)
                for key,value in [('path_maximum_step_radians',abs(steps).max()),('path_step_RMS_radians',np.sqrt(np.mean(steps**2)))]:
                    assert abs(float(value)-row['stages'][stage][key])<2e-9
                cross=np.sum(r[:,None]*np.diff(cdf,axis=1)*p[:,None]*m[None,:])
                assert abs(cross-complex(*row['stages'][stage]['cross']))<2e-12
            expected_gradient=max(1.,row['stages']['density']['cdf_product_gradient'])
            assert abs(expected_gradient-float(z['gradient_scale']))<max(2e-12,expected_gradient*2e-12)
            report['models']+=1
            return z

        if producer['stage']=='known':
            rows={r['label']:r for r in producer['cases']}
            for row in producer['cases']:
                if row['label']=='fixed_phase':assert row['exact_constant_decoder'];continue
                if row['label']=='invalid_target_rejected':assert row['rejected'];continue
                z=check(a.study/row['label']/'model.npz',row)
                if 'expected_kappa' in row:
                    width=z['high']-z['low'];bound=float(np.min(z['column_mass'][width>0]/width[width>0]))
                    assert abs(bound-row['kappa'])<2e-7 and row['stages']['variation']['cdf_product_gradient']<2e-7
                report['cases'].append(dict(label=row['label'],verified=True))
            for name in ('quarter_turn','conjugate'):
                assert abs(rows[name]['kappa']-rows['associated_continuous_phase']['kappa'])<2e-7
                assert abs(rows[name]['stages']['variation']['cdf_product_gradient']-rows['associated_continuous_phase']['stages']['variation']['cdf_product_gradient'])<2e-6
            report['known_analytic_optima_and_symmetries_verified']=True
        else:
            parent=a.workspace/'baselines/conditional_phase_feasibility_v1/evidence/real1'
            prior=load(parent/'report.json');old={r['label']:r for r in prior['cases']}
            for row in producer['cases']:
                previous=old[row['label']]
                assert row['root_hz']==previous['root_hz']
                for h,r in enumerate(row['harmonics']):
                    z=check(a.study/row['label']/f'{h+1:03d}'/'model.npz',r,
                        (np.load(parent/row['label']/f'{h+1:03d}'/'transport.npz'),previous['harmonics'][h]))
                    assert r['order']==h+1 and r['mean_product']==previous['harmonics'][h]['mean_product']
                inputs=np.load(parent/row['label']/'inputs.npz');hz=np.arange(1,289)*row['root_hz']
                for band in row['bands']:
                    lo,hi=band['band_Hz'];mask=(hz>=lo)&(hz<hi);den=np.sqrt(inputs['energy'][mask].sum(axis=0).prod())
                    for stage in ('parent','density','variation'):
                        value=sum(h['mean_product']*complex(*h['stages'][stage]['cross']) for h,yes in zip(row['harmonics'],mask) if yes)/den
                        assert abs(value-complex(*band[stage]))<2e-12
                report['cases'].append(dict(label=row['label'],models=288));print('PASS independent576 LP certificates',row['label'],flush=True)
            harmonics=[h for r in producer['cases'] for h in r['harmonics']]
            for key,summary in producer['summary'].items():
                for stage in ('parent','density','variation'):
                    value=np.quantile([h['stages'][stage][key] for h in harmonics],[0,.5,.9,.99,1])
                    assert np.array_equal(value,np.array(summary[stage]['quantiles']))
                assert sum(h['stages']['variation'][key]<h['stages']['parent'][key] for h in harmonics)==summary['variation_improves_vs_parent']
            report['all_source_summary_fields_verified']=True
        report.update(result='independent_conditional_slope_audit_passed',producer_sha256=sha(a.study/'report.json'),auditor_sha256=sha(__file__),declared_identical_1025_point_paths_verified=True)
        save(a.out/'report.json',report);print(report['result'],flush=True)
    except BaseException as exc:
        report.update(result='failed',error=repr(exc));save(a.out/'report.json',report);raise


if __name__=='__main__':main()

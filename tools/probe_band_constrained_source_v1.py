"""Known-only constraints prototype, independently checked against analytic/QP optima."""
import argparse
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import save,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('workspace','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from scipy.optimize import minimize
    from band_constrained_source_v1.solver import solve,assess_groups
    a.out.mkdir(parents=True,exist_ok=False);repo=Path(__file__).resolve().parents[1]
    r=dict(result='running',sources={},cases=[]);packets={}
    try:
        for name in ('tools/band_constrained_source_v1/__init__.py','tools/band_constrained_source_v1/solver.py',
            'tools/probe_band_constrained_source_v1.py','tools/research_archive_v1.py'):
            dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(repo/name,dest);r['sources'][name]=sha(dest)
        eps=.015;identity=np.eye(4);groups=[np.arange(2),np.arange(2,4)]
        definitions=[('identity',identity,np.array([.8,-.4,.2,.3]),identity),
            ('weak_band',identity,np.array([.8,-.4,2e-5,3e-5]),identity),
            ('zero_band',identity,np.array([.8,-.4,0.,0.]),identity)]
        d=np.array([[1.,.2,-.1,.1],[.1,1.1,.1,-.2],[.2,-.1,.9,.3],[-.1,.2,.1,1.2]])
        definitions.append(('mixed',d,d@np.array([.8,-.4,.2,.3]),np.diag([1.,1.2,.8,1.5])))
        for label,design,target,prior in definitions:
            result=solve(design,target,prior,groups,epsilon=eps)
            q=result['coefficients'];assert result['converged'] and result['original_strict_fidelity_passed']
            direct=[float(np.linalg.norm((design@q-target)[g])/np.linalg.norm(target[g])) if np.linalg.norm(target[g]) else float(np.linalg.norm((design@q-target)[g])) for g in groups]
            assert np.max(abs(np.array(direct)-result['relative_or_zero_target_absolute_errors']))<2e-12
            if label!='mixed':
                independent=(1-eps)*target
                difference=float(np.max(abs(q-independent)))
                assert difference<2e-9,(label,difference)
            else:
                constraints=[]
                for g in groups:
                    scale=np.linalg.norm(target[g]);matrix=design[g]/scale;value=target[g]/scale
                    constraints.append(dict(type='ineq',fun=lambda x,m=matrix,y=value:eps**2-np.sum((m@x-y)**2),
                        jac=lambda x,m=matrix,y=value:-2*m.T@(m@x-y)))
                independent=minimize(lambda x:.5*x@prior@x,np.linalg.solve(design,target),
                    jac=lambda x:prior@x,method='SLSQP',constraints=constraints,
                    options=dict(ftol=1e-13,maxiter=500))
                assert independent.success,independent.message
                difference=float(np.max(abs(q-independent.x)));assert difference<2e-7,difference
            assert result['stationarity']<2e-9
            # This is a numerical dual check, not interval-certified feasibility.
            assert result['nominal_gap']>-2e-9 and result['nominal_gap']<2e-8
            r['cases'].append(dict(label=label,iterations=result['iterations'],relative_errors=direct,
                independently_computed_coefficient_difference=difference,primal_cost=result['primal_cost'],
                nominal_gap=result['nominal_gap'],stationarity=result['stationarity']))
            packets[label+'_design']=design;packets[label+'_target']=target;packets[label+'_coefficients']=q
            print('CONSTRAINED_KNOWN',label,result['iterations'],direct,flush=True)
        impossible=np.eye(4);impossible[3]=0
        rejected=solve(impossible,np.array([1.,.2,.3,.5]),identity,groups,iterations=300)
        assert not rejected['converged'] and not rejected['original_strict_fidelity_passed']
        r['infeasible_control']=dict(iterations=rejected['iterations'],converged=False,
            original_strict_fidelity_passed=False,relative_errors=rejected['relative_or_zero_target_absolute_errors'].tolist())
        # Regression: a tiny nonzero error on a zero target is not a 2% error.
        mask_groups=[np.array([0]),np.array([1])]
        target=np.array([1.,0.]);tiny=np.array([.01,1e-16])
        norms,absolute,mixed,passed=assess_groups(tiny,target,mask_groups)
        assert np.array_equal(norms,[1.,0.]) and np.array_equal(absolute,tiny)
        assert mixed[1]<.02 and passed.tolist()==[True,False]
        assert assess_groups(np.array([.01,0.]),target,mask_groups)[3].tolist()==[True,True]
        assert not assess_groups(np.array([.02,0.]),target,mask_groups)[3][0]
        assert not assess_groups(np.array([0.,1e-100]),np.zeros(2),mask_groups)[3][1]
        assert not assess_groups(np.array([0.,1e-300]),np.zeros(2),mask_groups)[3][1]
        assert assess_groups(np.array([0.,1e-302]),np.array([0.,1e-300]),mask_groups)[3].all()
        r['zero_target_contract']=dict(exact_zero_required=True,tiny_nonzero_rejected=True,
            original_2_percent_boundary_strict=True,relative_error_undefined_at_zero=True)
        mutations=[('fractional_indices',dict(groups=[np.array([0.,1.1]),np.array([2,3])])),
            ('float_indices',dict(groups=[np.array([0.,1.]),np.array([2,3])])),
            ('boolean_indices',dict(groups=[np.array([False,True]),np.array([2,3])])),
            ('duplicate_indices',dict(groups=[np.array([0,1]),np.array([1,3])])),
            ('outside_indices',dict(groups=[np.array([0,1]),np.array([2,4])])),
            ('scalar_indices',dict(groups=[np.array(0),np.array([1,2,3])])),
            ('nonfinite_tolerance',dict(tolerance=float('nan'))),
            ('infinite_tolerance',dict(tolerance=float('inf'))),
            ('fractional_iterations',dict(iterations=2.5)),
            ('boolean_iterations',dict(iterations=True)),
            ('nonfinite_epsilon',dict(epsilon=float('nan')))]
        r['invalid_contract_rejections']=[]
        for label,overrides in mutations:
            args=dict(groups=groups);args.update(overrides)
            try:solve(identity,np.ones(4),identity,**args)
            except ValueError:r['invalid_contract_rejections'].append(label)
            else:raise AssertionError('Invalid contract accepted: '+label)
        np.savez_compressed(a.out/'known.npz',**packets)
        r.update(result='known_only_band_constrained_source_prototype_verified',verification_passed=True,
            constraints_have_declared_1_5_percent_margin_to_original_2_percent_gate=True,
            source_data_calibration_or_original_objective_not_replaced=True,
            no_vehicle_fit_or_new_audio_or_C_or_promotion=True,large_scale_resources_and_operator_adjoint_pending=True,
            packet_sha256=sha(a.out/'known.npz'),new_C1_source_eligible_for_statistics=False)
        save(a.out/'report.json',r);print(r['result'],flush=True)
    except BaseException as error:r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise


if __name__=='__main__':main()

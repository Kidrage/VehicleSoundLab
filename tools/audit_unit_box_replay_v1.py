"""Certify all analytic/replayed unit transforms and original saved inputs."""
import argparse
import json
from pathlib import Path
import shutil
import sys

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
args=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(args.workspace/'tools/ipm_deps'),str(args.workspace/'tools/qp_deps'),str(args.workspace/'tools/python_deps')]
import numpy as np
import scipy.sparse as sp
from drive_evidence_v1.sources import sha
from quintic_phase_v1.model import QuinticAbsoluteModel
from orthogonal_band_v1.operator import OrthogonalBand
from aperture_model_v1.forward import real_rows
from joint_trust_v1.constraints import Region
from joint_trust_v1.osqp_backend import linear_system
from radial_majorizer_v1.geometry import quadratic
from joint_radial_majorizer_v1.audit import geometry
from unit_box_qp_v1.audit import check,certificate_function


def load(path):return json.loads(path.read_text(encoding='utf-8'))
def save(path,value):path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')


args.out.mkdir(parents=True,exist_ok=False)
r=dict(schema='vsl.unit-box-replay-audit/1',result='running',sources={},controls=[],replays=[],
    nonlinear_estimator_rerun=False,quadratic_solver_rerun=False,truth_read=False,real_audio_read=False,model_exported=False,runtime_changed=False)
try:
    replay=args.workspace/'references/analysis/unit_box_qp_v1/replay1';observed=load(replay/'report.json')
    assert observed['result']=='all3_original_failed_QPs_pass_original_certificate'
    sources={Path(__file__),repo/'tools/unit_box_qp_v1/audit.py',repo/'tools/joint_radial_majorizer_v1/audit.py'}
    for name,digest in observed['sources'].items():
        assert sha(repo/name)==sha(replay/'exact_sources'/name)==digest;sources.add(repo/name)
    for path in sources:
        rel=path.relative_to(repo);dest=args.out/'exact_sources'/rel;dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,dest);r['sources'][rel.as_posix()]=sha(path)
    r['replay_report_sha256']=sha(replay/'report.json');certificate=certificate_function(repo/'tools/audit_interior_qp_v1.py')
    for item in observed['controls']['analytic_cases']:
        label=item['id'];q=item['certificate']
        if label=='coupled':
            gram=np.eye(2);g=np.array([-3.,-2.]);weighted=np.eye(2)
            matrix=sp.csc_matrix([[1.,0.],[0.,1.],[1.,1.]])
            lower=np.array([-3.,-3.,-np.inf]);upper=np.array([3.,3.,2.])
        else:
            radius=2**-16 if label=='small_trust' else 1.
            diagonal=np.array([1.,.2,0. if label=='singular' else .01]);gram=np.diag(diagonal);weighted=np.diag(np.sqrt(diagonal))
            target=np.array([0.,0.,0.]) if label=='zero' else np.array([2.,-3.,.4]) if label in ('strict_active','small_trust') else np.array([.2,-.3,0. if label=='singular' else .4])
            g=-gram@(target*radius);matrix=sp.eye(3,format='csc');lower=np.full(3,-radius);upper=-lower
        checked=check(q,gram,g,weighted,matrix,lower,upper,certificate);assert checked['success']
        r['controls'].append(dict(id=label,certificate=checked))
    parent=args.workspace/'references/analysis/joint_radial_majorizer_v1/fit1';fitted=load(parent/'fit.json')
    assert observed['parent_report_sha256']==sha(parent/'report.json') and observed['parent_fit_sha256']==sha(parent/'fit.json')
    inputs=np.load(parent/'input.npz');time,audio,initial=(inputs[k] for k in ('time','audio','initial_parameters'))
    plan=load(parent/'effective_plan.json');settings=load(parent/'effective_settings.json');variant=load(repo/'research/minority_phase_v1_plan.json')
    model=QuinticAbsoluteModel(time,plan,variant,[]);model.original.aperture=OrthogonalBand(len(time),plan)
    outer,amplitude=model.unpack(initial);scales=np.array(fitted['scales']);target=real_rows(model.original.aperture.apply(audio[:,0]))
    for row in fitted['history']:
        if row['iteration'] in (5,14,15):
            case=replay/('step'+str(row['iteration']));saved=np.load(case/'input.npz');q=load(case/'new_QP.json')
            assert load(case/'old_failed_QP.json')==row['qp']
            value,jacobian=model.prediction(outer,amplitude,True);matrix=np.column_stack((jacobian,model.design(outer)))*scales[None,:]
            gram,g,weighted,rhs=quadratic(value-target,matrix,row['stage_scale'])
            _,_,_,errors,_,roundoff=geometry(value-target,matrix,row['stage_scale'])
            ranged,lo,hi=linear_system(Region(model,outer,amplitude,scales,row['radius'],settings))
            for name,array in dict(gram=gram,gradient=g,weighted=weighted,rhs=rhs,matrix=ranged.toarray(),lower=lo,upper=hi).items():assert np.array_equal(array,saved[name])
            assert float(saved['radius'])==row['radius']
            checked=check(q,gram,g,weighted,ranged,lo,hi,certificate);assert checked['success']
            r['replays'].append(dict(iteration=row['iteration'],certificate=checked,geometry_errors=errors,factor_gradient_roundoff=roundoff,input_exact=True))
        if row['accepted']:outer,amplitude=np.array(row['candidate_outer']),np.array(row['candidate_absolute_amplitudes'])
    assert len(r['controls'])==6 and len(r['replays'])==3
    r.update(result='six_analytic_and_three_original_QP_transforms_independently_certified',all3_passed=True,
        original_factor_relative_failed_steps=[x['iteration'] for x in r['replays'] if not x['factor_gradient_roundoff']['original_gate1e12_passed']],
        original_dense_started=False,full_goal_complete=False)
except Exception as exc:
    r.update(result='failed',error=repr(exc));raise
finally:save(args.out/'report.json',r)
print(json.dumps(dict(result=r['result'],original_relative_failed_steps=r['original_factor_relative_failed_steps'])),flush=True)

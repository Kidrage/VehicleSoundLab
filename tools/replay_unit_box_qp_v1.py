"""Controls first, then exactly the three saved failed QPs, no nonlinear fit."""
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
from drive_evidence_v1.sources import sha
from quintic_phase_v1.model import QuinticAbsoluteModel
from orthogonal_band_v1.operator import OrthogonalBand
from aperture_model_v1.forward import real_rows
from joint_trust_v1.constraints import Region
from joint_trust_v1.osqp_backend import linear_system
from radial_majorizer_v1.geometry import quadratic
from unit_box_qp_v1.solver import solve_system
from unit_box_qp_v1.checks import controls as control_checks


def load(path):return json.loads(path.read_text(encoding='utf-8'))
def save(path,value):path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')


args.out.mkdir(parents=True,exist_ok=False)
r=dict(schema='vsl.unit-box-qp-replay/1',result='running',sources={},replays=[],truth_read=False,
    nonlinear_fit=False,real_audio_read=False,model_exported=False,runtime_changed=False)
try:
    parent=args.workspace/'references/analysis/joint_radial_majorizer_v1/fit1'
    prior=load(parent/'report.json');fitted=load(parent/'fit.json');assert prior['result']=='known_joint_majorizer_rejected'
    sources={Path(__file__),repo/'research/unit_box_qp_v1_plan.json'}
    sources.update((repo/'tools/unit_box_qp_v1').glob('*.py'))
    for name,digest in prior['sources'].items():
        assert sha(repo/name)==sha(parent/'exact_sources'/name)==digest;sources.add(repo/name)
    for path in sources:
        rel=path.relative_to(repo);dest=args.out/'exact_sources'/rel;dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,dest);r['sources'][rel.as_posix()]=sha(path)
    settings=load(parent/'effective_settings.json');r['controls']=control_checks(settings)
    assert r['controls']['passed']
    r['parent_report_sha256']=sha(parent/'report.json');r['parent_fit_sha256']=sha(parent/'fit.json')
    inputs=np.load(parent/'input.npz');time,audio,initial=(inputs[k] for k in ('time','audio','initial_parameters'))
    plan=load(parent/'effective_plan.json');variant=load(repo/'research/minority_phase_v1_plan.json')
    model=QuinticAbsoluteModel(time,plan,variant,[]);model.original.aperture=OrthogonalBand(len(time),plan)
    outer,amplitude=model.unpack(initial);scales=np.asarray(fitted['scales'])
    target=real_rows(model.original.aperture.apply(audio[:,0]))
    failures=[x['iteration'] for x in fitted['history'] if not x['qp']['success']];assert failures==[5,14,15]
    for row in fitted['history']:
        if row['iteration'] in failures:
            value,jacobian=model.prediction(outer,amplitude,True)
            design=np.column_stack((jacobian,model.design(outer)))*scales[None,:]
            gram,g,weighted,rhs=quadratic(value-target,design,row['stage_scale'])
            region=Region(model,outer,amplitude,scales,row['radius'],settings);matrix,lower,upper=linear_system(region)
            case=args.out/('step'+str(row['iteration']));case.mkdir()
            np.savez_compressed(case/'input.npz',gram=gram,gradient=g,weighted=weighted,rhs=rhs,
                matrix=matrix.toarray(),lower=lower,upper=upper,radius=row['radius'])
            save(case/'old_failed_QP.json',row['qp'])
            step,q=solve_system(gram,g,weighted,rhs,matrix,lower,upper,row['radius'],settings)
            save(case/'new_QP.json',q)
            r['replays'].append(dict(iteration=row['iteration'],radius=row['radius'],success=q['success'],
                status=q['status'],input_sha256=sha(case/'input.npz'),new_QP_sha256=sha(case/'new_QP.json'),
                normalized_stationarity=q['normalized_dual_stationarity'],primal=q['constraint_violation'],
                dual_sign=q['inequality_dual_sign_violation'],complementarity=q['maximum_complementarity']))
            print(json.dumps(r['replays'][-1]),flush=True)
        if row['accepted']:outer,amplitude=np.asarray(row['candidate_outer']),np.asarray(row['candidate_absolute_amplitudes'])
    passed=all(x['success'] for x in r['replays']);assert len(r['replays'])==3
    r.update(result='all3_original_failed_QPs_pass_original_certificate' if passed else 'unit_box_replay_rejected',
        all3_passed=passed,new_nonlinear_fit_permitted=passed,original_dense_started=False,full_goal_complete=False,
        limits=['Exact unit transformation of three fixed saved QPs only; not new phase or sound quality qualification',
            'Old failed steps/source retained; native success alone is insufficient'])
except Exception as exc:
    r.update(result='failed',error=repr(exc));raise
finally:save(args.out/'report.json',r)

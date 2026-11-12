"""Diagnose a finite primal active-set/null-space least-squares refinement."""
import argparse
import json
from pathlib import Path
import shutil
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace', type=Path, required=True)
parser.add_argument('--parent', type=Path, required=True)
parser.add_argument('--qr-replay', type=Path, required=True)
parser.add_argument('--refined-replay', type=Path, required=True)
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()
repo = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(args.workspace/'tools/ipm_deps'), str(args.workspace/'tools/qp_deps'),
    str(args.workspace/'tools/python_deps')]
import numpy as np
from drive_evidence_v1.sources import sha
from observed_topology_v1.fixtures import make
from quintic_phase_v1.model import QuinticAbsoluteModel
from aperture_model_v1.forward import real_rows
from joint_trust_v1.constraints import Region
from joint_trust_v1.osqp_backend import linear_system
from interior_qp_v1.backend import inequalities
from interior_qp_v1.active_set import polish


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


args.out.mkdir(parents=True, exist_ok=False)
report = dict(schema='vsl.qp-active-geometry/1', result='running', sources={}, cases=[],
    real_audio_read=False, real_source_permitted=False, qualification_changed=False,
    nonlinear_estimator_rerun=False, quadratic_solver_rerun=False, dual_linear_solves=True)
try:
    parent = load(args.parent/'report.json')
    sources = {Path(__file__), repo/'tools/interior_qp_v1/active_set.py', repo/'research/active_qp_v1_plan.json'} | {repo/name for name in parent['sources']}
    for relative, digest in parent['sources'].items():
        assert sha(repo/relative) == sha(args.parent/'exact_sources'/relative) == digest
    for folder in (args.qr_replay, args.refined_replay):
        value = load(folder/'report.json')
        assert value['result'] == 'failed' and value['parent_report_sha256'] == sha(args.parent/'report.json')
        assert all(sha(repo/name) == digest for name, digest in value['sources'].items())
        sources.update(repo/name for name in value['sources'])
    for path in sources:
        relative = path.relative_to(repo)
        target = args.out/'exact_sources'/relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        report['sources'][relative.as_posix()] = sha(path)
    topology = load(repo/'research/observed_topology_v1_plan.json')
    base, variant = load(repo/topology['base_plan']), load(repo/topology['minority_plan'])
    case = next(row for row in topology['added_cases'] if row['id'] == 'unknown_thirty_six')
    time, audio, _, _ = make(case, base)
    plan = load(args.parent/'effective_plan.json')
    settings = load(repo/'research/interior_qp_v1_plan.json')
    trust = load(repo/settings['parent_plan'])
    model = QuinticAbsoluteModel(time, plan, variant, [])
    target = real_rows(model.original.aperture.apply(audio[:, 0]))
    row = parent['fit']['history'][19]
    previous = parent['fit']['history'][18]
    outer, absolute = np.asarray(previous['candidate_outer']), np.asarray(previous['candidate_absolute_amplitudes'])
    predicted, derivative = model.prediction(outer, absolute, True)
    residual = predicted-target
    matrix = np.column_stack((derivative, model.design(outer)))*np.asarray(parent['fit']['scales'])[None, :]
    ratio = residual/plan['soft_l1_scale']
    curvature = (1+ratio**2)**(-1.5)
    gram = matrix.T@(curvature[:, None]*matrix)
    gradient = matrix.T@(residual/np.sqrt(1+ratio**2))
    region = Region(model, outer, absolute, np.asarray(parent['fit']['scales']), row['radius'], trust)
    a, lower, upper = linear_system(region)
    rows, bounds, high, low = inequalities(a, lower, upper)
    scale = float(abs(gradient).max())
    h = (gram+gram.T)/(2*scale)
    settings.update(load(repo/'research/active_qp_v1_plan.json'))
    weighted = np.sqrt(curvature)[:, None]*matrix
    rhs = -(residual/np.sqrt(1+ratio**2))/np.sqrt(curvature)
    report['linear_term_relative_error'] = float(np.linalg.norm(weighted.T@rhs+gradient)/np.linalg.norm(gradient))
    assert report['linear_term_relative_error'] < 1e-10
    for label, folder in (('qr', args.qr_replay), ('refined', args.refined_replay)):
        value = load(folder/'replay_20.json')
        q = value['new_QP']
        x, z = np.asarray(q['primal_solution']), np.asarray(q['inequality_dual'])
        polished_x, polished_z, evidence = polish(gram, gradient, weighted, rhs, rows, bounds, x, settings)
        candidate_outer, candidate_absolute, _, feasibility = region.retract(polished_x)
        row_report = dict(id=label, replay_sha256=sha(folder/'replay_20.json'),
            refinement=evidence, maximum_primal_change=float(abs(polished_x-x).max()),
            initial_objective=q['objective'], retraction=feasibility,
            initial_native_solved=q['native_success'])
        report['cases'].append(row_report)
        np.savez_compressed(args.out/(label+'.npz'), initial_primal=x, polished_primal=polished_x,
            initial_inequality_dual=z, polished_inequality_dual=polished_z)
        print(json.dumps(row_report), flush=True)
    report.update(result='primal_active_set_geometry_diagnosed',
        limits=['This is an active-set linear refinement at saved QPs, not a nonlinear fit or an automatic qualification',
            'All original limits remain required; a failed projected certificate cannot be relabeled as success'])
except Exception as exc:
    report.update(result='failed', error=repr(exc))
    raise
finally:
    (args.out/'report.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n', encoding='utf-8', newline='\n')

"""Check whether certificate error lies in the contact-constraint dual span."""
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


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


args.out.mkdir(parents=True, exist_ok=False)
report = dict(schema='vsl.qp-dual-geometry/1', result='running', sources={}, cases=[],
    real_audio_read=False, real_source_permitted=False, qualification_changed=False,
    nonlinear_estimator_rerun=False, quadratic_solver_rerun=False, dual_linear_solves=True)
try:
    parent = load(args.parent/'report.json')
    sources = {Path(__file__)} | {repo/name for name in parent['sources']}
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
    for label, folder in (('qr', args.qr_replay), ('refined', args.refined_replay)):
        value = load(folder/'replay_20.json')
        q = value['new_QP']
        x, z = np.asarray(q['primal_solution']), np.asarray(q['inequality_dual'])
        slack = bounds-rows@x
        contact = np.flatnonzero(slack <= settings['maximum_primal_violation'])
        initial_error = h@x+gradient/scale+rows.T@z
        correction, _, rank, singular = np.linalg.lstsq(rows[contact].toarray().T, -initial_error, rcond=1e-12)
        polished = z.copy()
        polished[contact] += correction
        stationarity = float(abs(h@x+gradient/scale+rows.T@polished).max())
        sign = float(max(0., -polished.min()))
        complementarity = float(abs(polished*slack).max())
        primal = float(max(0., -slack.min()))
        all_numeric = bool(stationarity <= settings['maximum_normalized_stationarity']
            and primal <= settings['maximum_primal_violation'] and sign <= settings['maximum_primal_violation']
            and complementarity <= settings['maximum_complementarity'])
        row_report = dict(id=label, replay_sha256=sha(folder/'replay_20.json'), primal_unchanged=True,
            contact_threshold=settings['maximum_primal_violation'], contact_count=len(contact),
            contact_rank=int(rank), maximum_dual_change=float(abs(correction).max()),
            before_stationarity=float(abs(initial_error).max()), after_stationarity=stationarity,
            dual_sign_violation=sign, complementarity=complementarity, primal_violation=primal,
            original_numeric_certificate_passed=all_numeric, native_solved=q['native_success'])
        report['cases'].append(row_report)
        np.savez_compressed(args.out/(label+'.npz'), primal=x, old_inequality_dual=z,
            polished_inequality_dual=polished, contact_indices=contact, contact_singular_values=singular)
        print(json.dumps(row_report), flush=True)
    report.update(result='contact_dual_geometry_diagnosed',
        limits=['This is dual linear algebra at saved primals, not a nonlinear fit or an automatic qualification',
            'All original limits remain required; a failed projected certificate cannot be relabeled as success'])
except Exception as exc:
    report.update(result='failed', error=repr(exc))
    raise
finally:
    (args.out/'report.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n', encoding='utf-8', newline='\n')

"""Audit the full untruncated initial-score space before deciding to fit."""
import argparse
import json
from pathlib import Path
import shutil
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace', type=Path, required=True)
parser.add_argument('--native', type=Path, required=True)
parser.add_argument('--geometry', type=Path, required=True)
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()
repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(args.workspace/'tools/python_deps'))
import numpy as np
from drive_evidence_v1.sources import sha
from quintic_phase_v1.model import QuinticAbsoluteModel
from model_score_v1.invariance import check


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


args.out.mkdir(parents=True, exist_ok=False)
report = dict(schema='vsl.model-score-invariance/1', result='running', sources={},
    real_audio_read=False, truth_used=False, heldout_used=False, nonlinear_estimator_run=False,
    full_qualification=False, model_exported=False, runtime_changed=False)
try:
    geometry = load(args.geometry/'report.json')
    assert geometry['result'] == 'fixed_initial_score_geometry_and_linear_controls_passed'
    assert sha(args.native/'input.npz') == geometry['native_input_sha256']
    assert sha(args.native/'effective_plan.json') == geometry['native_plan_sha256']
    assert sha(args.geometry/'basis.npy') == geometry['basis']['sha256']
    paths = {Path(__file__), repo/'tools/model_score_v1/invariance.py'}
    for relative, digest in geometry['sources'].items():
        assert sha(repo/relative) == sha(args.geometry/'exact_sources'/relative) == digest
        paths.add(repo/relative)
    for path in paths:
        relative = path.relative_to(repo)
        target = args.out/'exact_sources'/relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        report['sources'][relative.as_posix()] = sha(path)
    plan = load(args.native/'effective_plan.json')
    variant = load(repo/'research/minority_phase_v1_plan.json')
    inputs = np.load(args.native/'input.npz')
    model = QuinticAbsoluteModel(inputs['time'], plan, variant, [])
    basis = np.load(args.geometry/'basis.npy', allow_pickle=False)
    result, reverse = check(model, inputs['initial_parameters'], basis, plan)
    np.save(args.out/'reverse_basis.npy', reverse, allow_pickle=False)
    report.update(result='fixed_initial_score_space_order_invariant' if result['passed'] else
        'fixed_initial_score_space_not_numerically_qualified',
        geometry_report_sha256=sha(args.geometry/'report.json'),
        controls=result, original_forward_tolerance_unchanged=True,
        reverse_basis_sha256=sha(args.out/'reverse_basis.npy'),
        fit_permitted=bool(result['passed']),
        limitations=['Equal full column spaces must have equal orthogonal projectors in exact arithmetic',
            'A failed permutation check invalidates this numerical construction, not physical identifiability',
            'Covariance orthogonality alone does not qualify a numerically selected subspace',
            'No singular-value cutoff, ridge, reduced source count or changed phase gate'])
    print(json.dumps(dict(result=report['result'], condition=geometry['basis']['normalized_adjoint_jacobian_condition'],
                          controls=result)), flush=True)
except Exception as exc:
    report.update(result='failed', error=repr(exc))
    raise
finally:
    (args.out/'report.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n',
                                      encoding='utf-8', newline='\n')

"""Qualify fixed observed-initialized source moments before one bounded fit."""
import argparse
import json
from pathlib import Path
import shutil
import sys
import time as timer

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace', type=Path, required=True)
parser.add_argument('--native', type=Path, required=True)
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()
repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(args.workspace/'tools/python_deps'))
import numpy as np
import scipy
from drive_evidence_v1.sources import sha
from quintic_phase_v1.model import QuinticAbsoluteModel
from model_score_v1.projection import build, ScoreAperture
from model_score_v1.checks import controls


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


args.out.mkdir(parents=True, exist_ok=False)
report = dict(schema='vsl.model-score-geometry/1', result='running', sources={},
    real_audio_read=False, truth_used=False, heldout_used=False,
    phase_estimator_qualified=False, model_exported=False, runtime_changed=False)
try:
    parent = load(args.native/'report.json')
    paths = {Path(__file__), repo/'research/model_score_v1_plan.json',
             *sorted((repo/'tools/model_score_v1').glob('*.py'))}
    for relative, digest in parent['sources'].items():
        assert sha(repo/relative) == sha(args.native/'exact_sources'/relative) == digest
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
    time, initial = (inputs[key] for key in ('time', 'initial_parameters'))
    model = QuinticAbsoluteModel(time, plan, variant, [])
    assert plan['observed_order_step'] == 1/plan['projection_cycles']
    report.update(native_plan_sha256=sha(args.native/'effective_plan.json'),
        native_input_sha256=sha(args.native/'input.npz'),
        native_report_sha256=sha(args.native/'report.json'),
        numeric_libraries=dict(numpy=np.__version__, scipy=scipy.__version__))
    started = timer.perf_counter()
    basis, metadata = build(model, initial)
    np.save(args.out/'basis.npy', basis, allow_pickle=False)
    report['basis'] = dict(**metadata, sha256=sha(args.out/'basis.npy'),
                          construction_seconds=timer.perf_counter()-started)
    operator = ScoreAperture(basis, model.original.aperture)
    report['controls'] = controls(model.original.aperture, operator, plan)
    report.update(result='fixed_initial_score_geometry_and_linear_controls_passed',
        limitations=['Fixed initial tangent can miss nonlinear waveform changes',
            'All initial tangent columns retained; no singular-value truncation or ridge',
            'Exact source-white covariance is not calibrated real coloured noise',
            'Linear projection controls do not qualify phase recovery or real timbre'])
    print(json.dumps(dict(result=report['result'], basis_condition=metadata['normalized_adjoint_jacobian_condition'],
                          controls=report['controls'])), flush=True)
except Exception as exc:
    report.update(result='failed', error=repr(exc))
    raise
finally:
    (args.out/'report.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n',
                                      encoding='utf-8', newline='\n')

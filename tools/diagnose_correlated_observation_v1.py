"""Qualify exact marginal noise geometry and measure out-of-band sensitivity before fitting."""
import argparse
import json
from pathlib import Path
import shutil
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace', type=Path, required=True)
parser.add_argument('--native', type=Path, required=True)
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()
repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(args.workspace/'tools/python_deps'))
from drive_evidence_v1.sources import sha
from aperture_model_v1.forward import Aperture
from correlated_observation_v1.marginal import MarginalAperture
from correlated_observation_v1.checks import controls

args.out.mkdir(parents=True, exist_ok=False)
report = dict(schema='vsl.correlated-observation-geometry/1', result='running', sources={},
    real_audio_read=False, phase_estimator_qualified=False, model_exported=False, runtime_changed=False)
try:
    plan_path = args.native/'effective_plan.json'
    plan = json.loads(plan_path.read_text(encoding='utf-8'))
    assert plan['observed_order_step'] == 1/plan['projection_cycles']
    paths = [Path(__file__), repo/'research/correlated_observation_v1_plan.json',
             repo/'tools/aperture_model_v1/forward.py', repo/'tools/native_observation_v1/noise_geometry.py',
             *sorted((repo/'tools/correlated_observation_v1').glob('*.py'))]
    for path in paths:
        relative = path.relative_to(repo)
        target = args.out/'exact_sources'/relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        report['sources'][relative.as_posix()] = sha(path)
    operator = MarginalAperture(Aperture(round(plan['cycles']*plan['samples_per_cycle']), plan))
    report['native_plan_sha256'] = sha(plan_path)
    report['controls'] = controls(operator, plan, plan['rules'])
    report.update(result='marginal_geometry_and_linear_controls_passed',
        limitations=['Overlapping windows remain correlated: marginal composite metric only',
            'All positive covariance eigenvalues retained; no ridge or singular-value threshold',
            'Observation-space gain does not equal amplification of actual raw source noise',
            'Known forward controls do not establish phase extraction or real timbre'])
    print(json.dumps(dict(result=report['result'], controls=report['controls'])), flush=True)
except Exception as exc:
    report.update(result='failed', error=repr(exc))
    raise
finally:
    (args.out/'report.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n',
                                      encoding='utf-8', newline='\n')

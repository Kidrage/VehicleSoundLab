"""Compute exact frequency/time observation-noise geometry without fitting audio."""
import argparse
import json
from pathlib import Path
import shutil
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace', type=Path, required=True)
parser.add_argument('--parent', type=Path, required=True)
parser.add_argument('--candidate', type=Path, required=True)
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()
repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(args.workspace/'tools/python_deps'))
from drive_evidence_v1.sources import sha
from aperture_model_v1.forward import Aperture
from native_observation_v1.noise_geometry import geometry


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


args.out.mkdir(parents=True, exist_ok=False)
report = dict(schema='vsl.native-noise-geometry-diagnosis/1', result='running', sources={},
    real_audio_read=False, real_source_permitted=False, qualification_changed=False,
    nonlinear_estimator_rerun=False, quadratic_solver_rerun=False, model_exported=False)
try:
    previous, candidate = load(args.parent/'effective_plan.json'), load(args.candidate/'effective_plan.json')
    sources = {Path(__file__), repo/'tools/aperture_model_v1/forward.py',
        repo/'tools/native_observation_v1/noise_geometry.py', repo/'research/native_noise_geometry_v1_plan.json'}
    for path in sources:
        relative = path.relative_to(repo)
        target = args.out/'exact_sources'/relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        report['sources'][relative.as_posix()] = sha(path)
    report['parent_plan_sha256'] = sha(args.parent/'effective_plan.json')
    report['candidate_plan_sha256'] = sha(args.candidate/'effective_plan.json')
    cases = []
    for label, plan in (('previous', previous), ('native', candidate)):
        frames = round(plan['cycles']*plan['samples_per_cycle'])
        operator = Aperture(frames, plan)
        hop = round(plan['projection_hop_cycles']*plan['samples_per_cycle'])
        cases.append(dict(id=label, **geometry(operator, hop)))
    report.update(result='exact_periodic_Hann_frequency_and_overlap_noise_geometry_measured', cases=cases,
        estimator_changed=False, whitening_applied=False,
        limits=['Energy-variance equivalent degrees of freedom are not matrix rank or phase-information count',
            'White Gaussian source-noise geometry does not calibrate real coloured engine texture',
            'No inference of an actual corrected phase, qualification or timbre from covariance alone'])
    print(json.dumps(dict(result=report['result'], cases=cases)), flush=True)
except Exception as exc:
    report.update(result='failed', error=repr(exc))
    raise
finally:
    (args.out/'report.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n', encoding='utf-8', newline='\n')

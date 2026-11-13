"""Independently replay the two preserved numerical failures and final operator identities."""
import argparse
import importlib.util
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
import numpy as np
from scipy.linalg import qr
from aperture_model_v1.forward import Aperture, real_rows
from native_observation_v1.noise_geometry import sample_rows
from drive_evidence_v1.sources import sha

args.out.mkdir(parents=True, exist_ok=False)
shutil.copy2(__file__, args.out/'executed_audit.py')
base = args.workspace/'references/analysis/correlated_observation_v1'
plan = json.loads((args.native/'effective_plan.json').read_text(encoding='utf-8'))
report = dict(schema='vsl.correlated-geometry-replay/1', result='running', cases=[],
    source_sha256=sha(Path(__file__)), original_gate=plan['rules']['maximum_forward_check_error'],
    nonlinear_estimator_rerun=False, real_audio_read=False, model_exported=False)
try:
    for name in ('geometry1', 'geometry2', 'geometry3'):
        path = base/name
        old = json.loads((path/'report.json').read_text(encoding='utf-8'))
        source = path/'exact_sources/tools/correlated_observation_v1/marginal.py'
        assert sha(source) == old['sources']['tools/correlated_observation_v1/marginal.py']
        module_spec = importlib.util.spec_from_file_location('preserved_'+name, source)
        module = importlib.util.module_from_spec(module_spec)
        module_spec.loader.exec_module(module)
        operator = module.MarginalAperture(Aperture(round(plan['cycles']*plan['samples_per_cycle']), plan))
        covariance_errors = []
        for index in (0, len(operator.starts)//2, len(operator.starts)-1):
            matrix = operator.sample_matrix(operator.starts[index])
            covariance_errors.append(float(abs(matrix@matrix.T/operator.real_noise_variance-np.eye(len(matrix))).max()))
        rng = np.random.default_rng(620178)
        raw = rng.normal(size=operator.frames)
        observed = rng.normal(size=2*len(operator.starts)*len(operator.bins))
        left, right = float(real_rows(operator.apply(raw))@observed), float(raw@operator.adjoint(observed))
        adjoint = abs(left-right)/max(1., abs(left), abs(right))
        tolerance = plan['rules']['maximum_forward_check_error']
        report['cases'].append(dict(id=name, preserved_report_sha256=sha(path/'report.json'),
            executed_operator_sha256=sha(source), original_result=old['result'],
            normalized_covariance_maximum_error=max(covariance_errors), adjoint_relative_error=adjoint,
            covariance_pass=bool(max(covariance_errors) <= tolerance), adjoint_pass=bool(adjoint <= tolerance)))
    first, second, final = report['cases']
    assert not first['covariance_pass'] and first['original_result'] == 'failed'
    assert second['covariance_pass'] and not second['adjoint_pass'] and second['original_result'] == 'failed'
    assert final['covariance_pass'] and final['adjoint_pass'] and final['original_result'] == 'marginal_geometry_and_linear_controls_passed'
    # The final square-root factor is verified against an independently
    # constructed periodic-Hann covariance, without forming an inverse Gram.
    original, _ = sample_rows(operator.base, 0)
    covariance = original@original.T/operator.real_noise_variance
    blocks = np.block([[operator.correlation, np.zeros_like(operator.correlation)],
                       [np.zeros_like(operator.correlation), operator.correlation]])
    covariance_error = float(abs(covariance-blocks).max())
    factor_error = float(abs(operator.factor@operator.factor.T-operator.correlation).max())
    assert covariance_error <= tolerance and factor_error <= tolerance
    q, _ = qr(original.T, mode='economic')
    time = np.arange(operator.size)/plan['samples_per_cycle']
    signal = .2*np.cos(2*np.pi*9.13*time+.31)
    native_energy = float(np.sum((original@signal)**2))
    projected_energy = float(operator.real_noise_variance*np.sum((q.T@signal)**2))
    actual = float(np.sum((operator.sample_matrix(0)@signal)**2))
    assert abs(actual-projected_energy) <= tolerance
    report.update(result='original_failures_and_final_marginal_geometry_independently_replayed',
        exact_sample_covariance_maximum_error=covariance_error, square_root_factor_Gram_maximum_error=factor_error,
        out_of_band_9_13=dict(native_energy=native_energy, canonical_energy=actual,
            independent_real_QR_energy=projected_energy, energy_increase_db=float(10*np.log10(actual/native_energy)),
            absolute_fraction_of_raw_source_norm_bound=actual/(operator.real_noise_variance*np.sum(signal**2))),
        original_gate_unchanged=True, phase_estimator_qualified=False)
    print(json.dumps(report), flush=True)
except Exception as exc:
    report.update(result='failed', error=repr(exc))
    raise
finally:
    (args.out/'report.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n', encoding='utf-8', newline='\n')

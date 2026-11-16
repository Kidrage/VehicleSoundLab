"""Run the unchanged complete-objective backend on a new known input packet."""
import numpy as np
from waveform_file_real_v1.evaluate import evaluate
from waveform_file_real_v1.resources import preflight
from waveform_file_full_v1.pipeline import solve_full
from waveform_file_full_v1.resources import Telemetry
from waveform_banded_v1.metric import supported_banded
from waveform_structured_v1.resources import process_memory


def solve(system, shared, reference, audio, directory):
    if not np.count_nonzero(audio):
        values = dict(q=np.zeros((shared.prior.size, 2)), wave_model_residual=np.zeros_like(audio))
        outputs, stats = evaluate(system, shared, audio, values, dict(stable_root_guard_passed=True), reference)
        bad = dict(q=np.ones((shared.prior.size, 2))*.01, wave_model_residual=np.ones_like(audio)*.01)
        _, badstats = evaluate(system, shared, audio, bad, dict(stable_root_guard_passed=True), reference)
        return dict(values, **outputs), dict(stats, zero_reference_bad_candidate=badstats)
    metric = system.metric; ledger = Telemetry(directory)
    resources = preflight(directory, len(audio), len(system.synthesis.positions), len(system.synthesis.orders), 64)
    assert resources['memory_passed'] and resources['disk_passed']
    factors = directory/'factors'; factors.mkdir()
    action = lambda e:e/metric.wave_scale**2+metric.adjoint(metric.forward(e))
    values, inverse, pipeline, initial, taus = solve_full(shared, lambda:supported_banded(metric),
        audio, action, factors, ledger, 64)
    inverse.close(); inverse_info = inverse.info()
    outputs, stats = evaluate(system, shared, audio, values, pipeline['base_solver'], reference)
    arrays = dict(values, **outputs, **taus, inverse_right_tau=inverse.right.tau, inverse_inner_tau=inverse.inner.tau,
        **{'base_'+name:value for name,value in initial.items()})
    info = dict(stats, pipeline=pipeline, solver=pipeline['base_solver'], inverse_info=inverse_info,
        resource_preflight=resources, resources=ledger.report(), process_memory=process_memory(),
        no_full_factor_arrays_in_capture=True)
    return arrays, info

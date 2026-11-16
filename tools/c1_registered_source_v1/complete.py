"""Complete declared terminal equations; no production solve/metric imports.

Derived from the preserved locked_source_guard_v1 complete audit. The explicit
C1 declared oracle replaces its SciPy equation oracle; SciPy comparisons stay
separate. No comparison or solver/fidelity gate is relaxed.
"""
from pathlib import Path
import numpy as np
from scipy import linalg
from research_archive_v1 import load, sha
from c1_declared_objective_v1.audit import verify as preparation
from locked_source_fit_v1.oracle import make as scipy_reference
from locked_source_guard_v1.measurement import declared, cross_operator, compare, fidelity as fidelity_gate
from observer_frequency_v1.reduced_oracle import synthesize
from observer_supported_v1.full_oracle import vec
from waveform_trace_audit_v1 import root_frobenius
from waveform_file_real_v1.audit_resources import inspect
from waveform_real_guard_v1.locked import audit_guard


def verify(directory):
    directory = Path(directory)
    source = load(directory/'report.json')
    assert sha(directory/'capture.npz') == source['capture_sha256']
    with np.load(directory/'capture.npz') as f:
        z = {name:f[name] for name in f.files}
    if 'prepared_file' in source:
        assert sha(source['prepared_file']) == source['prepared_sha256']
        with np.load(source['prepared_file']) as original:
            for name in original.files:
                assert np.array_equal(z[name], original[name]), name
    errors = {}
    def check(name, x, y, scale=1., gate=2e-8):
        x, y = np.asarray(x), np.asarray(y)
        assert x.shape == y.shape and np.isfinite(x).all() and np.isfinite(y).all(), name
        error = float(np.max(abs(x-y))/max(float(scale), 1e-300))
        errors[name] = error
        assert error < gate, (name, error, gate)
    def prepared_check(name, x, y):
        check('prepared_'+name, x, y, max(1., float(np.max(abs(y)))), gate=2e-12)
    oracle, prepared = preparation(z, prepared_check)
    sigma = float(z['sigma'])
    N, M, H = len(z['audio']), len(z['positions']), len(z['orders'])
    shape, n = (M, H, 2), 2*M*H
    L = np.linalg.cholesky(oracle.R)
    def inverse(v, transpose=False):
        nodes = oracle.nodes(np.asarray(v).ravel())
        return vec(linalg.solve_triangular(L if transpose else L.T,
            nodes.reshape(M, -1), lower=transpose).reshape(shape))
    q = z['fitted']/z['scale'][None]
    x = vec(q)
    root = vec((L.T@q.reshape(M, -1)).reshape(shape))
    check('independent_LR_interleave', x, z['q'].ravel(), max(1., np.linalg.norm(x)), gate=2e-12)
    check('packed_penalty_root', root, z['z'].ravel(), max(1., np.linalg.norm(root)), gate=2e-12)
    wave = synthesize(z['fitted'], z['positions'], z['orders'], N)
    check('all_order_scalar_waveform', wave, z['wave'])
    direct = np.r_[oracle.data_forward(inverse(root))-oracle.target(), root]
    dm = np.r_[z['wave_model_residual'].ravel()/sigma, vec(oracle.spectral(z['wave_model_residual']))]
    model = np.r_[dm, root]
    normal = inverse(oracle.data_adjoint(dm), True)+root
    trace = root_frobenius(oracle)
    normA = trace['root_Frobenius']
    check('complete_original_model', model, z['original_model_residual'], max(1., np.linalg.norm(oracle.target())))
    check('complete_original_adjoint', normal, z['original_model_normal'], max(1., normA*np.linalg.norm(oracle.target())))
    stable = float(np.linalg.norm(normal)/max(normA*np.linalg.norm(model), 1e-300))
    backward = float(np.linalg.norm(direct-model)/max(np.linalg.norm(oracle.target()), 1e-300))
    trace_difference = abs(normA-source['production_original_trace']['root_Frobenius'])/normA
    assert trace_difference < 2e-11
    error = oracle.data_forward(x)-oracle.target()
    gradient_nodes = oracle.nodes(oracle.data_adjoint(error))+(oracle.R@q.reshape(M, -1)).reshape(shape)
    gradient = float(np.linalg.norm(vec(gradient_nodes))/max(np.linalg.norm(oracle.data_adjoint(oracle.target())), 1e-300))
    check('complete_gradient', gradient, source['original_gradient'])
    check('complete_stable', stable, source['original_stable_complete_normal'])
    check('complete_backward', backward, source['original_backward_discrepancy'])
    residual = oracle.gap(x, source['residual_certificate']['residual_dual_scale'])
    restored = linalg.solve(oracle.R, oracle.nodes(oracle.data_adjoint(z['u'])).reshape(M, -1), assume_a='pos').reshape(shape)
    representer = dict(primal=float(error@error)+oracle.penalty(q),
        dual_lower_bound=float(2*oracle.target()@z['u']-z['u']@z['u'])-oracle.penalty(restored),
        gap_upper_bound=float((error+z['u'])@(error+z['u']))+oracle.penalty(q-restored))
    gaps = []
    for tag, certificate in (('residual', residual), ('representer', representer)):
        for name, value in certificate.items():
            check(tag+'_'+name, value, source[tag+'_certificate'][name], max(1., abs(value)))
        passed = bool(certificate['gap_upper_bound'] <= 1e-6*certificate['primal']+1e-10)
        assert passed == source[tag+'_certificate']['additional_gap_gate_passed']
        gaps.append(passed)
    qualified = bool(gradient < 2e-7 and stable <= 1e-11 and backward <= 1e-11
        and all(gaps) and source['solver']['stable_root_guard_passed'])
    assert qualified == source['solver_qualified']
    metrics = declared(z['audio'], z['wave'], float(z['amplitude']), z['weights'])
    metric_comparison = compare(metrics, source['metrics'], enforce=True)
    errors.update({'declared_'+k:v for k, v in metric_comparison['absolute_differences'].items()})
    fidelity = fidelity_gate(metrics)
    assert fidelity == source['fidelity_qualified'], 'fidelity_flag'
    scipy, old = scipy_reference(z['audio'], z['metric_target'], z['positions'], z['orders'], z['scale'])
    cross_metrics = cross_operator(scipy, old, wave, z['audio'])
    cross_comparison = compare(cross_metrics, source['metrics'])
    print('C1_TERMINAL_EQUATIONS', directory.name, qualified, fidelity, flush=True)
    history = []
    zs, es, gs, ds = (z[k] for k in ('history_z', 'history_wave', 'history_original_normal', 'delta_z'))
    assert zs.shape == gs.shape == (3, n, 2) and es.shape == (3, N, 2) and ds.shape == (2, n, 2)
    assert np.array_equal(zs[0], z['base_z']) and np.array_equal(es[0], z['base_wave_model_residual'])
    for j in range(3):
        dm = np.r_[es[j].ravel()/sigma, vec(oracle.spectral(es[j]))]
        gn = inverse(oracle.data_adjoint(dm), True)+zs[j].ravel()
        den = max(normA*np.linalg.norm(np.r_[dm, zs[j].ravel()]), 1e-300)
        check('history_original_normal_'+str(j), gn, gs[j].ravel(), max(den, 1.), gate=2e-12)
        consistent = oracle.data_forward(inverse(zs[j]))-oracle.target()
        back = float(np.linalg.norm(consistent-dm)/max(np.linalg.norm(oracle.target()), 1e-300))
        st = float(np.linalg.norm(gn)/den)
        history.append(dict(step=j, stable_complete_normal=st, backward=back,
            original_gates_passed=bool(st <= 1e-11 and back <= 1e-11)))
        if j == 0:
            side_den = normA/np.sqrt(2)*np.sqrt(np.sum(dm.reshape(-1, 2)**2, axis=0)+np.sum(zs[j]**2, axis=0))
            side_stable = np.linalg.norm(gn.reshape(n, 2), axis=0)/np.maximum(side_den, 1e-300)
            side_back = np.linalg.norm((consistent-dm).reshape(-1, 2), axis=0)/np.maximum(np.linalg.norm(oracle.target().reshape(-1, 2), axis=0), 1e-300)
            guard = audit_guard(z, source, oracle)
            check('base_guard_separate_LR_stable', guard['stable_LR'], source['solver']['stable_root_normal_relative'], gate=2e-12)
            check('base_guard_separate_LR_backward', guard['backward_LR'], source['solver']['root_backward_discrepancy'], gate=2e-12)
            guard['independent_declared_FFT_stable_LR'] = side_stable.tolist()
            guard['independent_declared_FFT_backward_LR'] = side_back.tolist()
            assert np.all(side_stable <= 1e-11) and np.all(side_back <= 1e-11)
            assert guard['stable_guard_passed'] and guard['backward_guard_passed']
        if j < 2:
            check('node_update_'+str(j), zs[j+1], zs[j]+ds[j], gate=2e-12)
            delta = synthesize(oracle.nodes(inverse(ds[j]))*z['scale'][None], z['positions'], z['orders'], N)
            check('wave_update_'+str(j), es[j+1], es[j]+delta, gate=2e-12)
    assert np.array_equal(zs[-1], z['z']) and np.array_equal(es[-1], z['wave_model_residual'])
    resources = inspect(source, directory)
    assert resources['registered_peak_bytes'] <= source['resource_preflight']['main_phase_array_allowance']
    if not np.count_nonzero(z['audio'][:, 1]):
        assert np.count_nonzero(z['q'][:, 1]) == np.count_nonzero(wave[:, 1]) == 0
    return dict(result='independent_c1_registered_source_case_verified', verification_passed=True,
        measurement_identity='vsl.c1-declared-objective/1', preparation_equations=prepared,
        all_qualified=bool(qualified and fidelity and resources['all_qualified']),
        solver_qualified=qualified, fidelity_qualified=fidelity, gradient=gradient,
        stable_original_complete_normal=stable, original_backward=backward,
        residual_certificate=residual, representer_certificate=representer, metrics=metrics,
        original_correction_history=history, independent_all_bin_trace=trace,
        trace_relative_difference=float(trace_difference), maximum_errors=errors,
        file_resource_audit=resources, independent_base_guard=guard,
        producer_sha256=sha(directory/'report.json'), capture_sha256=sha(directory/'capture.npz'),
        declared_saved_wave_metric_comparison=metric_comparison,
        retained_SciPy_metrics=cross_metrics, retained_SciPy_metric_comparison=cross_comparison,
        original_SciPy_failure_not_relabelled=True, certified_crossFFT_bound=False,
        no_sustained_voice_or_C_or_hearing_qualification=True)

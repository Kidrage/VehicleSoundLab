"""Every complete equation and positive original-target/context decomposition."""
import numpy as np
from locked_source_guard_v1.measurement import frame
from locked_source_fit_v1.oracle import make as scipy_reference
from observer_complete_v1.audit_oracle import curvature
from observer_frequency_v1.reduced_oracle import synthesize
from .oracle import make


def verify(d, check):
    assert np.array_equal(d['target'], d['audio'][2048:-2048]), 'new_target_slice'
    assert np.array_equal(d['metric_target'], d['legacy_target']), 'legacy_metric_target'
    assert np.array_equal(d['legacy_target'], d['legacy_audio'][2048:-2048]), 'legacy_target_slice'
    for key in ('audio', 'target', 'metric_target', 'weights', 'band_power', 'sigma', 'amplitude',
                'scale', 'positions', 'original_positions', 'probe_q', 'probe_rows', 'probe_rhs'):
        assert np.isfinite(d[key]).all(), key
    assert np.all(d['weights']>0) and np.all(d['scale']>0) and float(d['sigma'])>0 and float(d['amplitude'])>0
    oracle, old = make(d, check)
    forward, adjoint = oracle.forward(d['probe_q']), oracle.backward(d['probe_rows'])
    check('full_forward', d['probe_forward'], forward)
    check('full_adjoint', d['probe_adjoint'], adjoint)
    check('full_normal', d['probe_normal'], oracle.backward(forward))
    expected_rhs = np.r_[oracle.target(), np.zeros(len(d['probe_rhs'])-oracle.data_size)]
    check('full_RHS', d['probe_rhs'], expected_rhs)
    check('adjoint_inner_product', d['probe_forward']@d['probe_rows'], d['probe_q']@d['probe_adjoint'])
    check('independent_adjoint_inner_product', forward@d['probe_rows'], d['probe_q']@adjoint)
    check('full_coverage', d['coverage'], oracle.profile['full_coverage'])
    check('time_coverage', d['time_coverage'], oracle.profile['time_coverage'])
    original, positions = d['original_positions'], d['positions']
    expected_positions = np.r_[np.arange(-2048, 0, 256), original, original[-1]+np.arange(256, 2049, 256)]+2048
    assert np.array_equal(positions, expected_positions), 'full_original_node_geometry'
    check('original_curvature', oracle.D[8:-8, 8:-8], curvature(original))
    qp = oracle.nodes(d['probe_q'])
    wave = synthesize(qp*d['scale'][None], positions, d['orders'], len(d['audio']))
    target_wave = synthesize(qp[8:-8]*d['scale'][None], original, d['orders'], len(d['target']))
    check('retained_target_wave', wave[2048:-2048], target_wave)
    error = wave-d['audio']; spectrum = oracle.spectral(error)
    starts = np.arange(0, len(wave)-4096+1, 256)
    slots = np.where((starts>=2048)&(starts+4096<=len(wave)-2048))[0]
    assert np.array_equal(d['target_slots'], slots), 'target_slots'
    raw, _ = frame(target_wave-d['target'])
    target_rows = raw[old['keep']]*float(d['amplitude'])*d['weights'][None, :, None]
    check('retained_target_spectral_rows', spectrum[slots], target_rows)
    curve = oracle.D@qp.reshape(len(positions), -1)
    target_curve = curvature(original)@qp[8:-8].reshape(len(original), -1)
    target_loss = (np.sum((target_wave-d['target'])**2)/float(d['sigma'])**2
        +np.sum(abs(target_rows)**2)+.001*np.sum(abs(target_curve)**2)+.000001*np.sum(abs(qp[8:-8])**2))
    added = np.ones(len(starts), bool); added[slots] = False
    extras = (np.sum(error[:2048]**2)/float(d['sigma'])**2+np.sum(error[-2048:]**2)/float(d['sigma'])**2
        +np.sum(abs(spectrum[added])**2)+.001*(np.sum(abs(curve[:8])**2)+np.sum(abs(curve[-8:])**2))
        +.000001*(np.sum(abs(qp[:8])**2)+np.sum(abs(qp[-8:])**2)))
    assert extras >= 0
    check('positive_added_context_objective', np.sum(error**2)/float(d['sigma'])**2+np.sum(abs(spectrum)**2)+oracle.penalty(qp), target_loss+extras)
    # Report the original cross-operator comparison separately, preserving its failure.
    scipy, _ = scipy_reference(d['audio'], d['metric_target'], positions, d['orders'], d['scale'])
    previous_rhs = np.r_[scipy.target(), np.zeros(len(d['probe_rhs'])-scipy.data_size)]
    cross = float(np.max(abs(previous_rhs-d['probe_rhs']))/max(1., float(np.max(abs(previous_rhs)))))
    return oracle, dict(measurement_identity='vsl.c1-declared-objective/1',
        full_shape=[len(d['probe_rhs']), len(d['probe_q'])], frames=len(d['audio']), target_frames=len(d['target']),
        orders=len(d['orders']), nodes=len(positions), original_nodes=len(original),
        positive_added_objective=float(extras), complete_equations_verified=True,
        declared_RHS_max_absolute=float(np.max(abs(expected_rhs-d['probe_rhs']))),
        original_SciPy_reference_RHS_error=cross, original_SciPy_reference_RHS_gate_passed=cross<=2e-12,
        certified_crossFFT_bound=False, no_fit_or_source_fidelity_or_runtime_qualification=True)

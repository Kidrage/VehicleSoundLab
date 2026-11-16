"""Independent real full objective; no producer operator/adapter imports."""
import numpy as np
from locked_source_fit_v1.oracle import make
from observer_complete_v1.audit_oracle import curvature, full_frame
from observer_frequency_v1.reduced_oracle import synthesize


def verify(d, check):
    oracle, old = make(d['audio'], d['metric_target'], d['positions'], d['orders'], d['scale'])
    for name in ('weights', 'band_power', 'sigma', 'amplitude'): check('legacy_'+name, d[name], old[name])
    assert np.array_equal(d['floor_active'], old['floor_active'])
    check('full_forward', d['probe_forward'], oracle.forward(d['probe_q']))
    check('full_adjoint', d['probe_adjoint'], oracle.backward(d['probe_rows']))
    check('full_normal', d['probe_normal'], oracle.backward(oracle.forward(d['probe_q'])))
    check('full_RHS', d['probe_rhs'], np.r_[oracle.target(), np.zeros(len(d['probe_rhs'])-oracle.data_size)])
    check('adjoint_inner_product', d['probe_forward']@d['probe_rows'], d['probe_q']@d['probe_adjoint'])
    check('full_coverage', d['coverage'], oracle.profile['full_coverage'])
    check('time_coverage', d['time_coverage'], oracle.profile['time_coverage'])
    original, positions = d['original_positions'], d['positions']; size = len(d['target'])
    expected_positions = np.r_[np.arange(-2048, 0, 256), original, original[-1]+np.arange(256, 2049, 256)]+2048
    assert np.array_equal(positions, expected_positions)
    check('original_curvature', oracle.D[8:-8, 8:-8], curvature(original))
    qp = oracle.nodes(d['probe_q'])
    wave = synthesize(qp*d['scale'][None], positions, d['orders'], len(d['audio']))
    target_wave = synthesize(qp[8:-8]*d['scale'][None], original, d['orders'], size)
    check('retained_target_wave', wave[2048:-2048], target_wave)
    error = wave-d['audio']; spectrum = oracle.spectral(error)
    starts = np.arange(0, len(wave)-4096+1, 256)
    slots = np.where((starts>=2048)&(starts+4096<=len(wave)-2048))[0]
    assert np.array_equal(d['target_slots'], slots)
    raw, _ = full_frame(target_wave-d['target'])
    target_rows = raw[old['keep']]*old['amplitude']*old['weights'][None, :, None]
    check('retained_target_spectral_rows', spectrum[slots], target_rows)
    curve = oracle.D@qp.reshape(len(positions), -1)
    target_curve = curvature(original)@qp[8:-8].reshape(len(original), -1)
    target_loss = (np.sum((target_wave-d['target'])**2)/old['sigma']**2
        +np.sum(abs(target_rows)**2)+.001*np.sum(abs(target_curve)**2)+.000001*np.sum(abs(qp[8:-8])**2))
    added = np.ones(len(starts), bool); added[slots] = False
    extras = (np.sum(error[:2048]**2)/old['sigma']**2+np.sum(error[-2048:]**2)/old['sigma']**2
        +np.sum(abs(spectrum[added])**2)+.001*(np.sum(abs(curve[:8])**2)+np.sum(abs(curve[-8:])**2))
        +.000001*(np.sum(abs(qp[:8])**2)+np.sum(abs(qp[-8:])**2)))
    assert extras >= 0
    check('positive_added_context_objective', np.sum(error**2)/old['sigma']**2+np.sum(abs(spectrum)**2)+oracle.penalty(qp), target_loss+extras)
    return dict(full_shape=[len(d['probe_rhs']), len(d['probe_q'])], orders=len(d['orders']),
        nodes=len(positions), original_nodes=len(original), positive_added_objective=float(extras),
        forward_adjoint_normal_RHS_and_target_decomposition=True, no_fit_executed=True)

"""Independent analytic source/clock/bandwidth evidence, no adapter imports."""
import math
import numpy as np
from clock_c1_v1.audit_geometry import verify as geometry
from locked_source_tail_v1.audit_kernel import analytic


def verify(label, z, metadata, check):
    sizes = {'affine_unequal':4609, 'nonlinear_delay':4353, 'nonlinear_silent_right':4865, 'nonlinear_zero':4609}
    n = sizes[label]+4096; q = np.arange(n, dtype=float)
    x = np.unique(np.r_[np.arange(0, n, 256), n-1]).astype(float)
    y = 160.36+x/65536+(0 if label == 'affine_unequal' else 8e-8*np.sin(x/750))
    clock = {key.removeprefix('clock_'):value for key,value in z.items() if key.startswith('clock_')}
    assert np.array_equal(z['observed_clock_x'], x) and np.array_equal(z['observed_clock_y'], y)
    assert np.array_equal(clock['x'], x) and np.array_equal(clock['y'], y) and np.array_equal(z['phase_grid_indices'], q)
    gr = geometry(dict(clock, query=q, positions=z['source_coordinates']))
    slots = np.clip(np.searchsorted(x, q, side='right')-1, 0, len(x)-2)
    old = y[slots]+(q-x[slots])/(x[slots+1]-x[slots])*(y[slots+1]-y[slots])
    check('independent_old_PL_seconds', z['legacy_source_coordinates'], old, gate=2e-12, scale=1.)
    assert np.array_equal(z['legacy_target_source_coordinates'], z['legacy_source_coordinates'][2048:-2048])
    assert np.array_equal(z['target_source_coordinates'], z['source_coordinates'][2048:-2048])
    assert np.array_equal(z['target'], z['audio'][2048:-2048])
    assert np.array_equal(z['metric_target'], z['legacy_target']) and np.array_equal(z['legacy_target'], z['legacy_audio'][2048:-2048])
    orders = np.array([5, 65, 110, 140, 185, 300]); scale = np.array([.19, .13, .09, .08, .06, .04])[:, None]
    assert np.array_equal(z['orders'], orders) and np.array_equal(z['scale'], scale)
    assert np.array_equal(z['source_frequency'], orders*64.)
    coefficients = np.empty((6, 2), complex)
    for i, f in enumerate(orders*64.):
        coefficients[i, 0] = scale[i, 0]*complex(math.cos(.29*i), math.sin(.29*i))
        angle = 1.1+.81*i
        coefficients[i, 1] = .61*scale[i, 0]*complex(math.cos(angle), math.sin(angle))
        if label == 'nonlinear_delay':
            a = -2*math.pi*f*.00035
            coefficients[i, 1] = .63*coefficients[i, 0]*complex(math.cos(a), math.sin(a))
        if label == 'nonlinear_silent_right': coefficients[i, 1] = 0
        if label == 'nonlinear_zero': coefficients[i] = 0
    check('physical_analytic_coefficients', z['source_coefficients'], coefficients)
    k = np.arange(-512, 513, dtype=float)
    taps = 2*22000/48000*np.sinc(2*22000/48000*k)*np.i0(12*np.sqrt(1-(k/512)**2))/np.i0(12)
    taps /= math.fsum(taps)
    check('explicit_physical_source_FIR', z['source_filter_taps'], taps, gate=2e-12, scale=max(abs(taps)))
    # Clock coordinates are independently verified above; evaluate analytic audio
    # on the exact saved FP64 queries, avoiding an undeclared time-rounding change.
    source_peak = 0.
    for name, times in (('legacy_audio', z['legacy_source_coordinates']), ('audio', z['source_coordinates'])):
        expected = analytic(times-160., orders*64., coefficients, z['source_filter_taps'])
        peak = float(np.max(abs(expected))); source_peak = max(source_peak, peak)
        check('physical_source_'+name, z[name], expected, gate=2e-11, scale=peak)
    assert metadata['schema'] == 'vsl.c1-source-input/1'
    assert metadata['objective_metric_origin'] == 'explicit unchanged legacy metric_target'
    assert metadata['source_time_geometry'] == 'new common LR C1, distinct from legacy coordinates'
    # Independent extrema of dY/dX on every normalized cubic interval.
    c = clock['coefficients']; minimum, maximum = math.inf, -math.inf
    for j, h in enumerate(np.diff(x)):
        candidates = [0., h]
        if c[0, j] != 0:
            at = -c[1, j]/(3*c[0, j])
            if 0 < at < h: candidates.append(at)
        values = [float((3*c[0, j]*t+2*c[1, j])*t+c[2, j]) for t in candidates]
        minimum = min(minimum, *values); maximum = max(maximum, *values)
    assert minimum > 0
    b = metadata['bandwidth']; rates = [1/maximum, 1/minimum]; roots = [r/1024 for r in rates]
    exact = dict(native_rate_Hz=48000, native_Nyquist_Hz=24000., declared_source_FIR_nominal_cutoff_Hz=22000.,
        source_FIR_taps=1025, derivative_seconds_per_virtual_sample=[minimum, maximum],
        phase_grid_samples_per_source_second=rates, acoustic_root_Hz=roots,
        phase_grid_Nyquist_Hz=[r/2 for r in rates], nominal_grid_guard_Hz=.4*rates[0],
        highest_retained_order=300, highest_carrier_centre_Hz=[300*r for r in roots])
    for key, expected in exact.items(): check('bandwidth_'+key, b[key], expected)
    assert b['declared_source_FIR_nominal_cutoff_Hz'] < 24000 and b['declared_source_FIR_nominal_cutoff_Hz'] <= b['nominal_grid_guard_Hz']
    assert b['carrier_centre_is_not_strict_bandwidth'] and b['finite_FIR_is_not_brickwall']
    assert not any(b[k] for k in ('strict_alias_free_proof', 'actual_crank_RPM_identified', 'raw_fullband_preserved', 'physical_source_separation'))
    return dict(geometry=gr, derivative_extrema_seconds_per_virtual_sample=[minimum, maximum],
        original_and_new_source_same_physical_formula=True, analytic_peak=source_peak,
        nominal_bandwidth_not_strict_alias_proof=True)

"""Independent explicit taps/direct FIR/every offset; no producer imports."""
import math
import numpy as np
from locked_source_tail_v1.audit_kernel import sinc_sum


def verify(z, raw, source_start, positions, check):
    n = np.arange(-512, 513, dtype=float)
    taps = 2*22000/48000*np.sinc(2*22000/48000*n)*np.i0(12*np.sqrt(1-(n/512)**2))/np.i0(12.)
    taps /= math.fsum(taps)
    check('explicit_FIR', z['taps'], taps, scale=max(abs(taps)))
    first = math.floor((float(positions[0])-source_start)*48000+1e-6)-4800
    stop = math.ceil((float(positions[-1])-source_start)*48000-1e-6)+4801
    assert np.array_equal(z['crop'], [first, stop]) and 0 <= first < stop <= len(raw)
    assert int(z['radius']) == 2048 and float(z['beta']) == 20.
    filtered = np.column_stack([np.convolve(raw[first:stop, c], z['taps'], mode='same') for c in (0, 1)])
    peak = float(np.max(abs(filtered)))
    check('direct_full_FIR', z['filtered'], filtered, gate=2e-11, scale=peak)
    q = (positions-source_start-first/48000)*48000
    check('every_native_query', z['query'], q, gate=2e-12, scale=1.)
    centers = np.floor(q).astype(np.int64)
    assert centers.min()+1-2048 >= 512 and centers.max()+2048 < len(filtered)-512
    output = sinc_sum(z['filtered'], z['query'], 2048)
    check('every_source_sample', z['audio'], output, gate=2e-11, scale=peak)
    return dict(queries=len(q), source_filter_frames=len(filtered), FIR_taps=1025,
        genuine_context_avoids_FIR_boundary=True, every_query_independently_accumulated=True,
        filtered_source_peak=peak)


def bandwidth(clock, orders, actual, check):
    c = clock['coefficients']; low, high = math.inf, -math.inf
    for j, h in enumerate(np.diff(clock['x'])):
        t = [0., float(h)]
        if c[0, j] != 0:
            critical = -c[1, j]/(3*c[0, j])
            if 0 < critical < h: t.append(float(critical))
        values = [(3*c[0, j]*v+2*c[1, j])*v+c[2, j] for v in t]
        low, high = min(low, *values), max(high, *values)
    assert low > 0
    rates = [1/high, 1/low]; roots = [v/1024 for v in rates]
    expected = dict(native_rate_Hz=48000, native_Nyquist_Hz=24000.,
        declared_source_FIR_nominal_cutoff_Hz=22000., source_FIR_taps=1025,
        derivative_seconds_per_virtual_sample=[low, high],
        phase_grid_samples_per_source_second=rates, acoustic_root_Hz=roots,
        phase_grid_Nyquist_Hz=[v/2 for v in rates], nominal_grid_guard_Hz=.4*rates[0],
        highest_retained_order=int(max(orders)), highest_carrier_centre_Hz=[max(orders)*v for v in roots])
    for key, value in expected.items(): check('bandwidth_'+key, actual[key], value)
    assert 22000 < 24000 and 22000 <= actual['nominal_grid_guard_Hz']
    assert actual['carrier_centre_is_not_strict_bandwidth'] and actual['finite_FIR_is_not_brickwall']
    assert not any(actual[k] for k in ('strict_alias_free_proof', 'actual_crank_RPM_identified',
                                     'raw_fullband_preserved', 'physical_source_separation'))
    return expected

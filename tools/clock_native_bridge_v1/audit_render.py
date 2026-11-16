"""Independent every-query sinc sum and explicit-FIR/polyphase native check."""
import numpy as np
from scipy import signal
from native_clock_case_audit_v1.clock import kernel
from .audit_inverse import verify as inverse


def reconstruct(audio, query):
    radius = 128
    centers = np.floor(query).astype(np.int64)
    assert centers.min()+1-radius >= 0 and centers.max()+radius < len(audio)
    numerator = np.zeros((len(query), 2)); denominator = np.zeros(len(query))
    for offset in range(1-radius, radius+1):
        ids = centers+offset; distance = query-ids
        sinc = np.ones(len(query)); nz = distance != 0
        sinc[nz] = np.sin(np.pi*distance[nz])/(np.pi*distance[nz])
        weight = sinc*np.i0(12*np.sqrt(np.maximum(0, 1-(distance/radius)**2)))/np.i0(12)
        denominator += weight
        numerator += weight[:, None]*audio[ids]
    return numerator/denominator[:, None]


def verify(source, rendered, up, check, *, kind='C1'):
    count = int(source['count']); start = float(source['native_start'])
    ticks = np.arange(-128*up, (count-1)*up+128*up+1)
    times = start+ticks/(48000*up)
    assert np.array_equal(times, rendered['dense_times'])
    q = rendered['query']
    if kind == 'C1':
        result = inverse(source, times, q)
    else:
        positions = source['old_positions']; grid = source['query']
        assert times.min() >= positions[0] and times.max() <= positions[-1]
        k = np.clip(np.searchsorted(positions, times, side='right')-1, 0, len(positions)-2)
        expected = grid[k]+(times-positions[k])/(positions[k+1]-positions[k])*(grid[k+1]-grid[k])
        error = float(np.max(abs(q-expected))/1024); assert error <= 2e-11
        result = dict(all_queries=len(q), independent_inverse_max_cycles=error)
    audio = source['source'] if 'source' in source else source[kind+'_source']
    scale = float(np.max(abs(audio)))
    dense = reconstruct(audio, q-source['query'][0])
    check('all_dense_reconstruction', rendered['dense_wave'], dense, scale, 2e-11)
    taps = kernel(up)
    check('explicit_FIR', rendered['taps'], taps, float(np.max(abs(taps))), 2e-11)
    expected = signal.upfirdn(taps, rendered['dense_wave'], down=up, axis=0)[256:256+count]
    check('all_native_polyphase', rendered['native'], expected, scale, 2e-11)
    indices = np.unique(np.linspace(0, count-1, 33, dtype=int))
    direct = np.array([taps[::-1]@rendered['dense_wave'][i*up:i*up+len(taps)] for i in indices])
    check('direct_native_FIR', rendered['native'][indices], direct, scale, 2e-11)
    assert rendered['native'].shape == (count, 2)
    result.update(independent_dense_samples=len(q), independent_native_samples=count, direct_output_probes=len(indices))
    return result

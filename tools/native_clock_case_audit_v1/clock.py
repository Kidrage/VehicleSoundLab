"""Explicit scalar all-order basis, original Fourier model and FIR checks."""
import bisect
import math
import numpy as np
from scipy import signal


def kernel(up):
    middle = 128 * up
    ix = np.arange(-middle, middle + 1, dtype=float)
    rate = 48000 * up
    sinc = np.array([2 * 22000 / rate if k == 0 else
                     math.sin(2 * math.pi * 22000 * k / rate) / (math.pi * k) for k in ix])
    window = np.i0(12 * np.sqrt(np.maximum(0, 1 - (ix / middle) ** 2))) / np.i0(12)
    taps = sinc * window
    return taps / math.fsum(taps)


def scalar_wave(z, query):
    slot = min(bisect.bisect_right(z['positions'], query) - 1, len(z['positions']) - 2)
    fraction = (query - z['positions'][slot]) / (z['positions'][slot + 1] - z['positions'][slot])
    result = []
    for channel in (0, 1):
        terms = []
        for h in range(1, 289):
            left, right = z['fitted'][slot:slot + 2, h - 1, channel]
            coefficient = left + (right - left) * fraction
            angle = 2 * math.pi * math.remainder(h * query / 1024, 1)
            terms.append(coefficient.real * math.cos(angle) - coefficient.imag * math.sin(angle))
        result.append(math.fsum(terms))
    return result


def verify(z, native, rendered, up, check, gates):
    q = rendered['query']
    count = len(native['raw_native_target'])
    origin = float(z['source_coordinates'][0])
    relative = z['source_coordinates'] - origin
    ticks = np.arange(-128 * up, (count - 1) * up + 128 * up + 1)
    times = float(native['native_start']) - origin + ticks / (48000 * up)
    assert times[0] >= 0 and times[-1] <= relative[-1]
    slots = np.searchsorted(relative, times, side='right') - 1
    slots[slots == len(relative) - 1] = len(relative) - 2
    inverse = slots + (times - relative[slots]) / (relative[slots + 1] - relative[slots])
    check('all_inverse_cycles_' + str(up), q / 1024, inverse / 1024, 1.,
          gates['independent_inverse_cycles_max'])
    assert np.array_equal(q, native['query' + str(up)])
    assert np.array_equal(rendered['dense_times'], origin + times)
    probes = np.unique(np.r_[np.linspace(0, len(q) - 1, 97, dtype=int),
        np.clip(np.searchsorted(q, z['positions'])[:, None] + [-1, 0, 1], 0, len(q) - 1).ravel()])
    expected = []
    for index in probes:
        j = min(bisect.bisect_right(relative, float(times[index])) - 1, len(relative) - 2)
        value = j + (float(times[index]) - float(relative[j])) / float(relative[j + 1] - relative[j])
        check('scalar_inverse_cycles', q[index] / 1024, value / 1024, 1., gates['independent_inverse_cycles_max'])
        expected.append(scalar_wave(z, value))
    scale = float(np.max(np.sum(abs(z['fitted']), axis=1)))
    check('scalar_full288_basis_' + str(up), rendered['dense_wave'][probes], expected, scale,
          gates['scalar_basis_relative_coefficient_L1_max'])
    taps = kernel(up)
    check('explicit_FIR_' + str(up), rendered['taps'], taps, float(np.max(abs(taps))),
          gates['explicit_filter_and_direct_FIR_relative_source_max'])
    assert rendered['native'].shape == (count, 2)
    assert np.array_equal(rendered['native'], rendered['filtered_dense'][::up])
    indices = np.unique(np.linspace(0, count - 1, 33, dtype=int))
    direct = np.array([taps[::-1] @ rendered['dense_wave'][int(i) * up:int(i) * up + len(taps)]
                       for i in indices])
    check('selected_direct_FIR_' + str(up), rendered['native'][indices], direct, scale,
          gates['explicit_filter_and_direct_FIR_relative_source_max'])
    filtered = signal.upfirdn(taps, rendered['dense_wave'], down=up, axis=0)[256:256 + count]
    check('all_polyphase_native_' + str(up), rendered['native'], filtered, scale,
          gates['explicit_filter_and_direct_FIR_relative_source_max'])
    return dict(up=up, scalar_dense_probes=len(probes), direct_FIR_probes=len(indices),
                independently_filtered_output_frames=count,
                scalar_indices=probes, scalar_wave=np.asarray(expected),
                direct_indices=indices, direct_wave=direct, polyphase_native=filtered)


def integer_model(z, check, gate):
    probes = np.unique(np.r_[np.arange(0, len(z['audio']), 137), z['positions']]).astype(int)
    out = np.zeros((len(probes), 2))
    for node, position in enumerate(z['positions']):
        bins = np.zeros((1024, 2), complex)
        bins[1:289] = z['fitted'][node] / 2
        bins[-np.arange(1, 289)] = z['fitted'][node].conj() / 2
        cycle = (np.fft.ifft(bins, axis=0) * 1024).real
        weights = np.zeros(len(probes))
        if node:
            left = z['positions'][node - 1]
            mask = (probes >= left) & (probes <= position)
            weights[mask] = (probes[mask] - left) / (position - left)
        if node + 1 < len(z['positions']):
            right = z['positions'][node + 1]
            mask = (probes >= position) & (probes <= right)
            weights[mask] = (right - probes[mask]) / (right - position)
        out += weights[:, None] * cycle[probes % 1024]
    scale = float(np.max(np.sum(abs(z['fitted']), axis=1)))
    check('original_integer_Fourier_model', z['wave'][probes], out, scale, gate)
    return probes, out

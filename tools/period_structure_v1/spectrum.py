"""Fixed-window spectral observations in an existing acoustic coordinate."""
import numpy as np
from scipy import signal


def observe(audio, samples_per_cycle, root_hz, plan):
    size = round(plan['window_cycles'] * samples_per_cycle)
    hop = round(plan['hop_cycles'] * samples_per_cycle)
    starts = np.arange(0, len(audio) - size + 1, hop)
    if not len(starts):
        raise ValueError('Not enough measured samples for the declared spectral window')
    window = signal.windows.hann(size, sym=False)
    bins = size * plan['zero_padding']
    powers = np.array([abs(np.fft.rfft((audio[start:start+size] -
        audio[start:start+size].mean(axis=0)) * window[:, None], n=bins, axis=0))**2 /
        (window.sum()**2/2) for start in starts])
    orders = np.fft.rfftfreq(bins) * samples_per_cycle
    hz = orders * root_hz
    power = powers.mean(axis=0)
    keep = (hz >= plan['band_hz'][0]) & (hz < plan['band_hz'][1])
    channels = []
    for channel in range(2):
        db = 10*np.log10(np.maximum(power[:, channel], 1e-30))
        indices, properties = signal.find_peaks(db, prominence=plan['peak_prominence_db'])
        retained = keep[indices] & (db[indices] >= max(db[keep])+plan['peak_relative_db'])
        indices = indices[retained]
        prominence = properties['prominences'][retained]
        left, middle, right = db[indices-1], db[indices], db[indices+1]
        denominator = left-2*middle+right
        offset = np.divide(.5*(left-right), denominator, out=np.zeros_like(left), where=abs(denominator)>1e-12)
        located = orders[indices]+np.clip(offset, -.5, .5)*(orders[1]-orders[0])
        rows = [dict(order=float(order), hz=float(order*root_hz), relative_db=float(db[index]-max(db[keep])),
            prominence_db=float(prom), power=float(power[index, channel]))
            for order, index, prom in zip(located, indices, prominence)]
        channels.append(dict(peaks=rows, lattice=lattice(rows, plan)))
    return dict(frames=len(audio), window_samples=size, windows=len(starts),
        power_normalization='Coherent one-sided line power: 2*abs(FFT)**2/sum(Hann)**2; not integrated band PSD',
        bin_spacing_orders=float(orders[1]-orders[0]), true_window_resolution_orders=1/plan['window_cycles'],
        root_hz_for_display=root_hz, channels=channels), (orders, power, starts, powers)


def lattice(rows, plan):
    """Describe occupancy, excluding near-integer peaks from fractional evidence.

    Counts are not a detector or a p-value: dense/noisy spectra can fill any grid.
    Integer peaks must never count as evidence for all of their subharmonics.
    """
    orders = np.array([row['order'] for row in rows])
    powers = np.array([row['power'] for row in rows])
    integer_distance = abs(orders-np.round(orders))
    fractional = integer_distance >= plan['integer_guard_orders']
    result = dict(integer_peaks=int(np.sum(integer_distance <= plan['fraction_tolerance_orders'])),
        fractional_peaks=int(fractional.sum()), hypotheses={})
    for divisor in plan['denominators']:
        distance = abs(orders-np.round(orders*divisor)/divisor)
        matched = fractional & (distance <= plan['fraction_tolerance_orders'])
        result['hypotheses'][str(divisor)] = dict(noninteger_matches=int(matched.sum()),
            distinct_integer_neighborhoods=int(len(np.unique(np.floor(orders[matched]).astype(int)))),
            fractional_power_fraction=float(powers[matched].sum()/max(powers[fractional].sum(), 1e-30)),
            matched_orders=orders[matched].tolist(),
            warning='Descriptive occupancy only; harmonically nested grids, AM and noise are not engine-cycle identification')
    return result

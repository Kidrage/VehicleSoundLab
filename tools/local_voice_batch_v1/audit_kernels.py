"""Independent scalar/path/direct-demodulation checks, not production extractors.

Path, reconstruction and seeded sum descend from audit_F3_lift_voice_v1;
carrier coordinates are reconstructed here without calling the warp module.
"""
import math
import numpy as np
from scipy import signal
from sustain_osc_v1.oracle import Gaussian


def peaks(hz, power):
    db = 10*np.log10(np.maximum(power, 1e-30))
    indices, info = signal.find_peaks(db, prominence=4)
    rows = []
    for j, k in enumerate(indices):
        if not 35 <= hz[k] < 1200:
            continue
        before, middle, after = map(float, db[k-1:k+2])
        den = before-2*middle+after
        delta = .5*(before-after)/den if abs(den) > 1e-12 else 0
        rows.append((float(hz[k]+max(-.5, min(.5, delta))*48000/16384),
                     float(info['prominences'][j])))
    return rows


def path(nodes, times, initial, cap):
    score = [v['score']-(abs(math.log2(v['root']/initial))/.1)**2
             if abs(math.log2(v['root']/initial)) <= .1 else -math.inf for v in nodes[0]]
    links = []
    for i in range(1, len(nodes)):
        dt = times[i]-times[i-1]
        current, previous = [], []
        for v in nodes[i]:
            costs = []
            for u, s in zip(nodes[i-1], score):
                velocity = math.log2(v['root']/u['root'])/dt
                costs.append(s-.025*velocity**2 if abs(velocity) <= cap else -math.inf)
            j = max(range(len(costs)), key=costs.__getitem__)
            previous.append(j)
            current.append(costs[j]+v['score'])
        links.append(previous)
        score = current
    assert any(math.isfinite(s) for s in score)
    trace = [max(range(len(score)), key=score.__getitem__)]
    for link in reversed(links):
        trace.append(link[trace[-1]])
    return list(reversed(trace))


def carrier_rows(audio, order):
    starts = list(range(0, len(audio)-4096+1, 256))
    window = .5-.5*np.cos(2*np.pi*np.arange(4096)/4096)
    kernel = window*np.exp(-2j*np.pi*order*np.arange(4096)/1024)*2/math.fsum(window)
    values = np.array([np.sum(audio[s:s+4096]*kernel[:, None], axis=0)*
                       np.exp(-2j*np.pi*order*s/1024) for s in starts])
    return np.array(starts)+2048, values


def coherence(audio, order):
    _, values = carrier_rows(audio, order)
    return abs(values.mean(axis=0))/np.mean(abs(values), axis=0)


def rebuild(native, start, positions, cutoff):
    first = math.floor((positions[0]-start)*48000+1e-6)-4800
    stop = math.ceil((positions[-1]-start)*48000-1e-6)+4801
    assert 0 <= first < stop <= len(native)
    taps = signal.firwin(1025, cutoff, fs=48000, window=('kaiser', 12))
    filtered = np.column_stack([np.convolve(native[first:stop, c], taps, mode='same') for c in (0, 1)])
    dense = signal.resample_poly(filtered, 16, 1, axis=0, window=('kaiser', 8.6), padtype='line')
    at = (positions-start-first/48000)*48000*16
    return np.column_stack([np.interp(at, np.arange(len(dense)), dense[:, c]) for c in (0, 1)])


def coordinates(native, start, family, center, plan):
    times = np.array([v['seconds'] for v in family])
    roots = np.array([v['root_hz'] for v in family])
    cycles = np.r_[0., np.cumsum(np.diff(times)*(roots[1:]+roots[:-1])/2)]
    center_cycle = np.interp(center, times, cycles)
    edges = center_cycle+np.array([-.5, .5])*plan['aperture_cycles']
    assert cycles[0] <= edges[0] < edges[1] <= cycles[-1]
    first, stop = np.interp(edges, cycles, times)
    native_times = np.arange(round(first*48000), round(stop*48000)+1)/48000
    hz = np.interp(native_times, times, roots)
    phase = np.r_[0., np.cumsum((hz[1:]+hz[:-1])/(2*48000))]
    original_positions = np.interp(np.arange(int(phase[-1]*1024))/1024, phase, native_times)
    cutoff = min(14000., .38*1024*float(min(hz)))
    initial = rebuild(native, start, original_positions, cutoff)
    centers, observed = carrier_rows(initial, plan['phase_reference'])
    angle = np.unwrap(np.angle(observed[:, 0]))
    assert max(abs(np.diff(angle))) <= np.pi*.8
    correction = (angle-angle[0])/(2*np.pi*plan['phase_reference'])
    indices = np.arange(int(centers[0]), int(centers[-1])+1)
    corrected = indices/1024+np.interp(indices, centers, correction)
    assert min(np.diff(corrected)) > 0
    grid = np.arange(int(np.ceil(corrected[0]*1024)), int(np.floor(corrected[-1]*1024)))/1024
    at = np.interp(grid, corrected, indices)
    positions = np.interp(at, np.arange(len(original_positions)), original_positions)
    inferred = 1/(1024*np.diff(positions))
    cutoff = min(cutoff, .38*1024*float(min(inferred)))
    return positions, cutoff, float(np.median(inferred))


def seeded_samples(model, root, seed, indices):
    # Independent direct trigonometric sum at sparse times; no C recurrence.
    h, k = model['basis'].shape[:2]
    rng = Gaussian(seed)
    pc = np.array([rng.next() for _ in range(k)])
    residual = np.array([rng.next() for _ in range(h*4)]).reshape(h, 4)

    def coefficients():
        return np.einsum('hkc,k->hc', model['basis'], pc*np.sqrt(3/(2+model['rho'])))+np.einsum(
            'hcj,hj->hc', model['root'], residual*np.sqrt(3/(2+model['residual_rho']))[:, None])

    def advance():
        nonlocal pc, residual
        pc = model['rho']*pc+np.sqrt(1-model['rho']**2)*np.array([rng.next() for _ in range(k)])
        rho = model['residual_rho'][:, None]
        residual = rho*residual+np.sqrt(1-rho*rho)*np.array([rng.next() for _ in range(h*4)]).reshape(h, 4)

    left = coefficients()
    advance()
    right = coefficients()
    fraction, rows, selected = 0., [], set(indices)
    mean = model['mean'][:, ::2]+1j*model['mean'][:, 1::2]
    units = np.divide(mean, abs(mean), out=np.ones_like(mean), where=abs(mean) > 1e-15)
    for n in range(max(indices)+1):
        while fraction >= 1:
            fraction -= 1
            left = right
            advance()
            right = coefficients()
        if n in selected:
            value = model['mean']+left+fraction*(right-left)
            magnitudes = np.hypot(value[:, ::2], value[:, 1::2])
            oscillator = np.exp(2j*np.pi*(n*root/48000)*np.arange(1, h+1))
            rows.append(np.sum(magnitudes*np.real(units*oscillator[:, None]), axis=0))
        fraction += root/12000
    return np.array(rows)

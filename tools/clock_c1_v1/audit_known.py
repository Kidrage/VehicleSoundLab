"""Independent analytic fixtures, direct carriers and FIR/polyphase render."""
import math
import numpy as np
from scipy.signal import upfirdn
from locked_source_tail_v1.audit_kernel import analytic
from .audit_geometry import verify as geometry


def clock(q, origin, kind):
    y = origin+q/65536
    if kind == 'chirp':
        y += 1e-10*(q-8192)**2
    elif kind == 'modulated':
        y += 2e-5*np.sin(q/1700)
    elif kind == 'C0':
        for node, jump in zip((1024.25, 4096.5, 8192.125, 12288.75, 16384.3), (1e-8, -6e-9, 4e-9, -7e-9, 3e-9)):
            y += np.maximum(q-node, 0)*jump
    return y


def fixture(t, spec):
    output = np.zeros((len(t), 2))
    for channel in (0, 1):
        v = t-channel*spec['delay']
        cycles = spec['root']*v+spec['slope']*v*v/2+spec['pm']*np.sin(2*np.pi*.55*v)
        for j, order in enumerate((3, 5, 7, 11, 15)):
            gain = (.07, .2, .065, .04, .025)[j]*(spec['right_ratio'] if channel else 1)
            gain = gain*(1+spec['am']*np.sin(2*np.pi*(.7+.13*j)*v+.4*j+.7*channel))
            phase = 2*np.pi*order*cycles+.13*order+channel*spec['right_phase']
            phase += spec['relative_pm']*(j-2)*np.sin(2*np.pi*1.3*v+.2*channel)
            output[:, channel] += gain*np.real(np.exp(1j*phase))
    return output


def render(native, positions, cutoff):
    lo = math.floor(positions[0]*48000+1e-6)-4800
    hi = math.ceil(positions[-1]*48000-1e-6)+4801
    assert 0 <= lo < hi <= len(native)
    def taps(n, f, beta):
        j = np.arange(n)-(n-1)/2
        h = f*np.sinc(f*j)*np.i0(beta*np.sqrt(np.maximum(0, 1-(2*j/(n-1))**2)))/np.i0(beta)
        return h/math.fsum(h)
    h = taps(1025, 2*cutoff/48000, 12)
    filtered = np.column_stack([np.convolve(native[lo:hi, c], h, mode='same') for c in (0, 1)])
    kernel = np.r_[0., 16*taps(321, 1/16, 8.6)]
    dense = upfirdn(kernel, filtered, up=16, axis=0)[161:161+16*len(filtered)]
    q = (positions-lo/48000)*48000*16
    # Every query is >100ms from either artificial crop edge.
    return np.column_stack([np.interp(q, np.arange(len(dense)), dense[:, c]) for c in (0, 1)])


def heldout(d, audio):
    result = {}; first, last = d['query'][2048], d['query'][-2049]
    k = np.arange(4096); w = .5-.5*np.cos(2*np.pi*k/4096)
    starts = np.arange(0, len(audio)-4096+1, 256)
    at = starts+d['validation_query'][0]+2048
    for order in (3, 7):
        c, s = np.cos(2*np.pi*order*k/1024)*w, -np.sin(2*np.pi*order*k/1024)*w
        rows = np.array([(c@audio[j:j+4096]+1j*(s@audio[j:j+4096]))/1024*
            np.exp(-2j*np.pi*order*j/1024) for j in starts])
        result[str(order)] = {}
        for name, mask in dict(whole=np.ones(len(at), bool), before=at<first,
                target=(at>=first)&(at<=last), after=at>last).items():
            assert np.any(mask)
            z = rows[mask]
            result[str(order)][name] = dict(windows=int(mask.sum()),
                coherence=(abs(z.sum(axis=0))/abs(z).sum(axis=0)).tolist(),
                mean_amplitude=abs(z).mean(axis=0).tolist())
    return result


def verify_analytic(d, row):
    r = geometry(d)
    for key, q in (('y', d['x']), ('exact', d['query'])):
        assert np.max(abs(d[key]-clock(q, row['origin'], row['kind']))) < 2e-12
    coeff, f, taps = d['tone_coefficients'], d['frequencies'], d['taps']
    base = 160. if row['origin'] > 1 else 0.
    mono = np.repeat(coeff[:, :1], 2, axis=1)
    delay = coeff.copy(); delay[:, 1] *= np.exp(-2j*np.pi*f*.00035)
    maximum = 0.
    for name, co in (('stereo', coeff), ('mono', mono), ('zero', coeff*0), ('weak', coeff*1e-6), ('delayed', delay)):
        expected = analytic(d['positions']-base, f, co, taps)
        error = float(np.max(abs(expected-d['signal__'+name]))/max(np.sum(abs(co)), 1e-300))
        assert error < 2e-12
        maximum = max(maximum, error)
    truth = analytic(d['exact']-base, f, coeff, taps)
    assert np.max(abs(truth-d['truth']))/np.sum(abs(coeff)) < 2e-12
    wave = float(np.linalg.norm(d['signal__stereo']-d['truth'])/np.linalg.norm(d['truth']))
    assert abs(wave-row['wave_change_vs_analytic_NRMSE']) < 2e-12
    if row['kind'] != 'C0':
        assert wave < .005
    assert np.array_equal(d['signal__mono'][:, 0], d['signal__mono'][:, 1])
    assert not np.count_nonzero(d['signal__zero'])
    return dict(geometry=r, independent_tone_max_relative_L1=maximum, wave_NRMSE=wave)


def verify_recorded(d, original, row):
    r = geometry(d)
    rv = geometry(d, 'validation_query', 'validation_positions')
    centers = original['observed_centers']
    a = np.searchsorted(original['observed_indices'], centers)
    b = np.searchsorted(original['coarse_indices'], centers)
    assert np.array_equal(d['x'], 1024*original['observed_phase'][a])
    assert np.array_equal(d['y'], original['coarse_positions'][b])
    assert np.array_equal(d['query'], original['sample_indices'])
    assert np.array_equal(d['validation_query'], original['validation_indices'])
    maximum = 0.
    for name, positions in (('audio', 'positions'), ('validation_audio', 'validation_positions')):
        expected = render(original['native'], d[positions], row['cutoff'])
        error = float(np.max(abs(expected-d[name])))
        assert error < 2e-12
        maximum = max(maximum, error)
    h = heldout(d, d['validation_audio'])
    for order in h:
        for name, result in h[order].items():
            assert result['windows'] == row['heldout'][order][name]['windows']
            for key in ('coherence', 'mean_amplitude'):
                assert np.max(abs(np.asarray(result[key])-row['heldout'][order][name][key])) < 2e-12
    minimum = min(min(v['coherence']) for t in h.values() for v in t.values())
    spec = row['spec']; p = d['positions']
    residual = spec['root']*p+spec['slope']*p*p/2+spec['pm']*np.sin(2*np.pi*.55*p)-d['query']/1024
    std = float(np.std(residual))
    exact = fixture(p, spec)
    wave = float(np.linalg.norm(d['audio']-exact)/np.linalg.norm(exact))
    assert abs(std-row['cycle_residual_std']) < 2e-12
    assert abs(wave-row['analytic_wave_NRMSE']) < 2e-12
    assert minimum > .99 and std < .002 and wave < .005 and row['qualified']
    return dict(geometry=r, validation_geometry=rv, independent_render_max_FS=maximum,
        minimum_heldout_coherence=minimum, cycle_residual_std=std, analytic_wave_NRMSE=wave,
        all_original_known_gates_passed=True)

"""Known common/shape AM and an explicitly phase-detuned pure tone."""
import numpy as np
from scipy import signal


def cases(model, phase, frames, plan):
    t = np.arange(frames) / plan['sample_rate']
    h = np.arange(1, plan['harmonics'] + 1)
    freq = h * plan['sample_rate'] / plan['cycle_frames']
    signed = np.zeros(len(h))
    for band, (a, b) in enumerate(plan['bands']):
        signed[(freq >= a) & (freq < b)] = (-1)**band

    def oscillator(detune=0, common=False, shape=False):
        output = np.zeros((frames, 2))
        modulation = plan['known_AM_log_depth'] * np.sin(2*np.pi*plan['known_AM_hz']*t)
        for k, f in enumerate(freq):
            gain = np.exp(modulation * (1 if common else signed[k] if shape else 0))
            output += gain[:, None] * model['rms'][k] * np.cos(
                2*np.pi*f*(1+detune)*t[:, None] + phase[k])
        return output

    steady = oscillator()
    result = [('known_stationary_OSC', steady),
              ('known_fixed_detune', oscillator(plan['known_constant_detune'])),
              ('known_common_gain', oscillator(common=True)),
              ('known_shape_AM', oscillator(shape=True))]
    for seed in plan['known_noise_seeds']:
        rng = np.random.default_rng(seed)
        sos = signal.butter(4, 10000, fs=plan['sample_rate'], output='sos')
        noise = signal.sosfilt(sos, rng.normal(size=(frames+12000, 2)), axis=0)[12000:]
        noise *= np.sqrt(np.mean(steady**2)/np.mean(noise**2)) * 10**(plan['known_noise_relative_rms_db']/20)
        result.append(('known_stationary_noise_'+str(seed), steady+noise))
    return result


def fraction_control(frames, plan, config, origin):
    """Nominal/true demodulation distinguish clock drift from broadband energy."""
    cycle = plan['cycle_frames']; h = plan['coherence_tone_harmonic']
    delta = plan['coherence_tone_detune']; n = np.arange(frames)
    audio = np.cos(2*np.pi*h*(1+delta)*n/cycle+.7)
    size = config['cycles']*cycle
    centers = np.arange(2*cycle+origin, frames-2*cycle+1, plan['hop'])
    starts = centers-size//2
    window = np.ones(size) if config['kind']=='rect' else .5-.5*np.cos(2*np.pi*np.arange(size)/size)
    # Independent direct scalar DFT, not the FFT implementation under test.
    nominal = np.array([2/window.sum()*np.sum(audio[at:at+size]*window*
        np.exp(-2j*np.pi*h*(at+np.arange(size))/cycle)) for at in starts])
    corrected = nominal*np.exp(-2j*np.pi*h*delta*starts/cycle)
    def fraction(z): return float(abs(z.mean())**2/np.mean(abs(z)**2))
    # Exact finite-window mean and second moment of the two real-tone exponentials.
    kernel_plus = np.sum(window*np.exp(2j*np.pi*h*delta*np.arange(size)/cycle))/window.sum()
    kernel_minus = np.sum(window*np.exp(-2j*np.pi*h*(2+delta)*np.arange(size)/cycle))/window.sum()
    analytic = np.exp(.7j)*kernel_plus*np.exp(2j*np.pi*h*delta*starts/cycle)+\
        np.exp(-.7j)*kernel_minus*np.exp(-2j*np.pi*h*(2+delta)*starts/cycle)
    return dict(window=config['name'], origin_frame=origin,
                nominal_fraction=fraction(nominal), known_clock_corrected_fraction=fraction(corrected),
                analytic_fraction_error=abs(fraction(nominal)-fraction(analytic)),
                meaning='Known constant-amplitude single real tone; no noise or source AM. Exact imposed clock correction is a control, not an estimated real clock.')

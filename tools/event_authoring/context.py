"""Compare the same event against both neighbouring backgrounds, without fitting."""
import numpy as np
from scipy import signal

from .audio import read
from .band_scope import normalize
from .measure import observe


def probe(source, seconds, backgrounds, scope=None):
    scope = normalize(scope)
    x, rate, provenance = read(source, *seconds)
    if not .008 <= len(x)/rate <= 5:
        raise ValueError('One event crop must be 0.008–5 seconds')
    rows = []
    arrays = []
    for name, interval in backgrounds.items():
        if len(interval) != 2 or not (interval[1] <= seconds[0] or interval[0] >= seconds[1]):
            raise ValueError('Background intervals must not overlap the event')
        background, _, background_source = read(source, *interval)
        if len(background) < 960:
            raise ValueError('Background must contain at least 20 ms')
        observation, values = observe(x, background, scope)
        rows.append(dict(name=name, source=background_source,
            full_contrast_db=observation['event_to_background_db'],
            scoped_contrast_db=observation.get('scoped_event_to_background_db', observation['event_to_background_db']),
            observation=observation))
        arrays.append(values)
    peak = int(np.argmax(np.mean(x*x, axis=1)))
    report = dict(schema='vsl.event-context-probe/1', source=provenance,
        analysis_scope=scope, sample_peak_seconds=(provenance['first_frame']+peak)/rate,
        backgrounds=rows, fit_performed=False, physical_identity_confirmed=False,
        limits=['Contrasts depend on the explicitly selected backgrounds; none is selected automatically.',
                'A contrast above 3 dB alone does not identify an afterfire or isolate a physical source.',
                'Positive PSD excess is a statistical estimate, not a cleaned event waveform.'])
    return report, arrays


def plot(source, seconds, event, backgrounds, scope, arrays, output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    x, rate, origin = read(source, *seconds)
    clock = np.arange(len(x))/rate + origin['first_frame']/rate
    fig, axes = plt.subplots(3, 1, figsize=(11, 7), layout='constrained')
    # Display channel powers, preserving antiphase stereo instead of cancelling it.
    envelope = np.sqrt(signal.convolve(np.mean(x*x, axis=1), np.ones(48)/48, mode='same'))
    axes[0].plot(clock, envelope, lw=.7)
    axes[0].set(ylabel='1 ms RMS / FS', title='Original context and explicitly selected intervals')
    for ax in axes[:2]:
        ax.axvspan(*event, color='#bd572d', alpha=.25)
        for i, (name, interval) in enumerate(backgrounds.items()):
            ax.axvspan(*interval, color=('#347ca0', '#51934d')[i % 2], alpha=.2)
    f, t, z = signal.stft(x, rate, nperseg=960, noverlap=720, axis=0, boundary=None, padded=False)
    p = np.mean(abs(z)**2, axis=1)
    selected = (f >= 60) & (f <= 14000)
    mesh = axes[1].pcolormesh(t+seconds[0], f[selected],
        10*np.log10(np.maximum(p[selected], 1e-12)), shading='auto', vmin=-90, vmax=-20)
    axes[1].set(ylabel='Frequency / Hz', xlabel='Original time / s')
    fig.colorbar(mesh, ax=axes[1], label='STFT power / dB FS')
    for (name, _), (frequency, power, background, _, *_) in zip(backgrounds.items(), arrays):
        axes[2].plot(frequency, 10*np.log10(np.maximum(background, 1e-16)), label=name+' background')
    axes[2].plot(arrays[0][0], 10*np.log10(np.maximum(arrays[0][1], 1e-16)), color='black', label='event crop')
    if scope['mode'] == 'band':axes[2].axvspan(scope['low_hz'], scope['high_hz'], color='#bd572d', alpha=.1)
    axes[2].set(xlim=(60, 14000), xlabel='Frequency / Hz', ylabel='PSD / dB FS per Hz')
    axes[2].legend();fig.savefig(output, dpi=150);plt.close(fig)

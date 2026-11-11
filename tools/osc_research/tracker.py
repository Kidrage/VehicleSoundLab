"""Shared-frequency sinusoidal tracks with separate complex L/R amplitudes.

These tracks describe one recording excerpt, not a general RPM/load model.
The sum of channel powers selects candidates without cancelling anti-phase
content. A track may be present in just one channel. No samples or residual
waveforms enter the reconstruction, which uses interpolated AM/FM oscillators.
"""
from dataclasses import dataclass
import numpy as np
from scipy import signal
from scipy.optimize import linear_sum_assignment

from sinusoidal_experiment import add_interval


@dataclass(frozen=True)
class Settings:
    window: int = 4096
    hop: int = 256
    zero_padding: int = 4
    lower_hz: float = 80
    upper_hz: float = 14000
    prominence_db: float = 8
    separation_bins: float = 3
    dynamic_range_db: float = 70
    sidelobe_guard: float = 1.5


def candidates(frame, sr, count, settings):
    """Return frequency and independent amplitudes/phases at the frame centre."""
    n, channels = frame.shape
    padded_n = n * settings.zero_padding
    # Pad symmetrically BEFORE centring: all phases refer to sample n//2,
    # including fractional frequencies. Padding after roll corrupts that phase.
    win = signal.windows.hann(n, sym=False)
    offset = (padded_n - n) // 2
    padded = np.pad(frame * win[:, None], ((offset, offset), (0, 0)))
    spectrum = np.fft.rfft(np.roll(padded, -padded_n // 2, axis=0), axis=0)
    power = np.sum(abs(spectrum) ** 2, axis=1)
    bins = signal.find_peaks(10 * np.log10(power + 1e-30),
        prominence=settings.prominence_db,
        distance=max(1, round(settings.separation_bins * settings.zero_padding)))[0]
    bins = bins[(bins > settings.lower_hz * padded_n / sr) &
                (bins < min(settings.upper_hz, sr * .46) * padded_n / sr) &
                (bins < len(power) - 2)]
    bins = bins[np.argsort(power[bins])[::-1]]
    accepted, support = [], []
    for k in bins:
        if power[k] < power.max()*10**(-settings.dynamic_range_db/10):
            continue
        q = np.log(power[k-1:k+2] + 1e-30)
        denominator = q[0] - 2*q[1] + q[2]
        delta = np.clip(.5*(q[0]-q[2])/denominator
                        if abs(denominator) > 1e-12 else 0, -.5, .5)
        frequency = (k + delta) * sr / padded_n
        # Zero padding reveals Hann sidelobes as local peaks. Reject peaks
        # explained by leakage from stronger accepted tones; otherwise a lone
        # sinusoid incorrectly generates many extra oscillators. This guard is
        # deliberately conservative and can mask weak real neighbours.
        if support:
            frequencies = np.array([a[0] for a in support])
            strengths = np.array([a[1] for a in support])
            def response(distance):
                return abs(np.sinc(distance)+.5*np.sinc(distance-1)+.5*np.sinc(distance+1))
            leakage = np.sum(strengths*(response((frequency-frequencies)*n/sr)+
                                         response((frequency+frequencies)*n/sr)))
            if np.sqrt(power[k]) <= settings.sidelobe_guard*leakage:
                continue
        # Cubic Lagrange interpolation of the centred complex transform.
        # This estimates both channels at the SAME off-bin frequency.
        u = delta
        weights = np.array([-u*(u-1)*(u-2)/6, (u+1)*(u-1)*(u-2)/2,
                            -(u+1)*u*(u-2)/2, (u+1)*u*(u-1)/6])
        z = weights @ spectrum[k-1:k+3] * (2 / win.sum())
        row = np.zeros(1+channels*2)
        row[0] = frequency
        row[1::2] = abs(z)
        row[2::2] = np.angle(z)
        accepted.append(row)
        support.append((frequency, np.sqrt(power[k])))
        if len(accepted) == count:
            break
    return np.array(accepted).reshape(-1, 1+channels*2)


def render_interval(out, center, sr, hop, left, right):
    for channel in range(out.shape[1]):
        indices = [0, 1 + 2*channel, 2 + 2*channel]
        add_interval(out[:, channel], center, hop, sr, left[indices], right[indices])


def synthesize(audio, sr, count=64, settings=Settings()):
    audio = np.asarray(audio)
    if audio.ndim == 1:
        audio = audio[:, None]
    out = np.zeros_like(audio, dtype=float)
    previous = None
    old_center = None
    matched = born = died = observed = 0
    for center in range(settings.window//2, len(audio)-settings.window//2, settings.hop):
        current = candidates(audio[center-settings.window//2:center+settings.window//2],
                             sr, count, settings)
        observed += len(current)
        if previous is not None:
            used_a, used_b = set(), set()
            if len(previous) and len(current):
                cost = abs(previous[:, None, 0] - current[None, :, 0]) / np.maximum(
                    16, previous[:, None, 0] * .045)
                rows, cols = linear_sum_assignment(cost)
                for i, j in zip(rows, cols):
                    if cost[i, j] > 1:
                        continue
                    render_interval(out, old_center, sr, settings.hop, previous[i], current[j])
                    used_a.add(i)
                    used_b.add(j)
                    matched += 1
            for i, a in enumerate(previous):
                if i not in used_a:
                    end = a.copy()
                    end[1::2] = 0
                    end[2::2] += 2*np.pi*a[0]*settings.hop/sr
                    render_interval(out, old_center, sr, settings.hop, a, end)
                    died += 1
            for j, b in enumerate(current):
                if j not in used_b:
                    start = b.copy()
                    start[1::2] = 0
                    start[2::2] -= 2*np.pi*b[0]*settings.hop/sr
                    render_interval(out, old_center, sr, settings.hop, start, b)
                    born += 1
        previous, old_center = current, center
    frames = len(range(settings.window//2, len(audio)-settings.window//2, settings.hop))
    return out, dict(analysed_frames=frames, mean_support_per_frame=observed/max(frames, 1),
                     matched_intervals=matched, births=born, deaths=died,
                     maximum_frequency_support=count, channel_oscillator_budget=count*audio.shape[1])


def independent(audio, sr, count=64, settings=Settings()):
    rendered, statistics = [], []
    for channel in range(audio.shape[1]):
        value, stats = synthesize(audio[:, channel:channel+1], sr, count, settings)
        rendered.append(value[:, 0])
        statistics.append(stats)
    return np.column_stack(rendered), dict(channel_tracks=statistics,
        maximum_union_frequency_support=count*audio.shape[1],
        channel_oscillator_budget=count*audio.shape[1])

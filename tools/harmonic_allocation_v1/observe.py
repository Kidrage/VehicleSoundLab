"""Common-center harmonic observations; descriptive fractions, no source labels."""
import numpy as np


def coefficients(audio, plan, config, origin):
    cycle, hop = plan['cycle_frames'], plan['hop']
    size = cycle * config['cycles']
    support = 2 * cycle
    centers = np.arange(support + origin, len(audio) - support + 1, hop)
    starts = centers - size // 2
    window = (np.ones(size) if config['kind'] == 'rect' else
              .5 - .5 * np.cos(2 * np.pi * np.arange(size) / size))
    harmonics = np.arange(1, plan['harmonics'] + 1)
    bins = harmonics * config['cycles']
    frames = audio[starts[:, None] + np.arange(size)] * window[None, :, None]
    z = np.fft.rfft(frames, axis=1)[:, bins] * 2 / window.sum()
    # Absolute acoustic-cycle origin, shared by both observed channels.
    z *= np.exp(-2j * np.pi * starts[:, None] * harmonics[None, :] / cycle)[:, :, None]
    errors = []
    for frame in sorted({0, len(starts) // 2, len(starts) - 1}):
        for h in (4, 36, 102, 170):
            phase = 2 * np.pi * bins[h] * np.arange(size) / size
            value = (np.cos(phase) - 1j * np.sin(phase)) @ frames[frame] * 2 / window.sum()
            value *= np.exp(-2j * np.pi * starts[frame] * harmonics[h] / cycle)
            floor = max(float(abs(z[frame]).max()) * 1e-6, 1e-20)
            errors.append(float(np.max(abs(value - z[frame, h]) / np.maximum(abs(z[frame, h]), floor))))
    return centers, starts, z, max(errors)


def band_statistics(z, plan):
    hz = np.arange(1, plan['harmonics'] + 1) * plan['sample_rate'] / plan['cycle_frames']
    masks = np.array([(hz >= a) & (hz < b) for a, b in plan['bands']])
    power = np.einsum('thc,bh->tbc', abs(z)**2 / 2, masks)
    coherent = np.einsum('hc,bh->bc', abs(z.mean(axis=0))**2 / 2, masks)
    fraction = coherent / power.mean(axis=0)
    # Split-half phase agreement is another descriptive, possibly negative, readout.
    split = len(z) // 2
    cross = np.real(z[:split].mean(axis=0).conj() * z[split:].mean(axis=0)) / 2
    agreement = np.einsum('hc,bh->bc', cross, masks) / power.mean(axis=0)
    return power, fraction, agreement


def shape_motion(power, plan):
    """Remove common log gain and linear trend; explicit slow DFT projection."""
    logs = 10 * np.log10(np.maximum(power, 1e-30))
    shape = logs - logs.mean(axis=1, keepdims=True)
    n = len(shape)
    design = np.column_stack((np.ones(n), np.linspace(-1, 1, n)))
    flat = shape.reshape(n, -1)
    motion = (flat - design @ np.linalg.lstsq(design, flat, rcond=None)[0]).reshape(shape.shape)
    hz = np.fft.rfftfreq(n, plan['hop'] / plan['sample_rate'])
    keep = (hz >= plan['slow_hz'][0]) & (hz <= plan['slow_hz'][1])
    z = np.fft.rfft(motion, axis=0)
    slow = np.fft.irfft(z * keep[:, None, None], n=n, axis=0)
    # Independent scalar trig sum of the selected DFT coefficients.
    t = np.arange(n)
    direct = np.zeros_like(slow)
    for k in np.flatnonzero(keep):
        phase = 2 * np.pi * k * t / n
        cosine, sine = np.cos(phase), np.sin(phase)
        direct += 2 / n * (cosine[:, None, None] * np.einsum('t,tbc->bc', cosine, motion) +
                          sine[:, None, None] * np.einsum('t,tbc->bc', sine, motion))
    error = float(np.max(abs(slow - direct)) / max(float(abs(slow).max()), 1e-12))
    return motion, slow, error, hz[keep]


def compare(slow_by_window):
    rows = []
    names = list(slow_by_window)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            x, y = slow_by_window[a], slow_by_window[b]
            px, py = np.mean(x*x, axis=(0, 1)), np.mean(y*y, axis=(0, 1))
            defined = (np.sqrt(px) > .01) & (np.sqrt(py) > .01)
            correlation = np.divide(np.mean(x*y, axis=(0, 1)), np.sqrt(px*py),
                                    out=np.zeros(2), where=defined)
            rows.append(dict(windows=[a, b], defined_LR=defined.tolist(),
                             correlation_LR=correlation.tolist(),
                             difference_rms_db_LR=np.sqrt(np.mean((x-y)**2, axis=(0, 1))).tolist()))
    return rows

"""Unit-amplitude carriers and sparse real/quadrature envelope controls."""
import numpy as np

RATE = 48000


def design(modes, frames, knots=1, quadrature=False, sweep_seconds=0.):
    if not isinstance(frames, (int, np.integer)) or frames < 2048:
        raise ValueError('At least2048 integer native frames required')
    if not isinstance(knots, (int, np.integer)) or not 1 <= knots <= 9:
        raise ValueError('One through nine sparse knots required')
    if not modes or len(modes) > 12 or not np.isfinite(sweep_seconds) or sweep_seconds < 0:
        raise ValueError('One through twelve modes and finite nonnegative sweep required')
    t = np.arange(frames)/RATE
    seconds = np.linspace(0, frames/RATE, knots) if knots > 1 else np.array([0.])
    eye = np.eye(knots)
    hats = np.column_stack([np.interp(t, seconds, row) for row in eye])
    columns, labels = [], []
    for i, mode in enumerate(modes):
        hz, end, phase = (float(mode[k]) for k in ('hz', 'end_hz', 'phase'))
        if not np.isfinite([hz, end, phase]).all() or not 0 < min(hz, end) <= max(hz, end) < RATE/2:
            raise ValueError('Finite oscillator frequencies below Nyquist required')
        frequency = hz+(end-hz)*np.minimum(1, t/sweep_seconds) if sweep_seconds else np.full(frames, hz)
        angle = phase+2*np.pi*np.r_[0., np.cumsum(frequency[:-1])]/RATE
        for axis, carrier in [('sin', np.sin(angle)), ('cos', np.cos(angle))][:2 if quadrature else 1]:
            columns.extend((carrier[:, None]*hats).T)
            labels.extend(dict(mode=i, axis=axis, knot=j) for j in range(knots))
    return np.column_stack(columns), dict(frames=int(frames), sample_rate=RATE,
        knots_seconds=seconds.tolist(), quadrature=bool(quadrature), columns=labels,
        modes=[{k: float(m[k]) for k in ('hz', 'end_hz', 'phase')} for m in modes],
        sweep_seconds=float(sweep_seconds), old_amplitudes_used=False)


def training_mask(frames):
    return (np.arange(frames)//480) % 4 != 3

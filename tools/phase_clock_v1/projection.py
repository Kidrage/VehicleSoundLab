"""Two-cycle phase observation, with independent-carrier diagnostics."""
import numpy as np
from exterior_clock_v1.warp import CYCLE, render_positions


def carrier_rows(audio, reference=5, cycles=2, orders=20):
    size = cycles * CYCLE
    starts = np.arange(0, len(audio) - size + 1, 256)
    if len(starts) < 3:
        raise ValueError('Insufficient complete local projection windows')
    window = .5 - .5 * np.cos(2 * np.pi * np.arange(size) / size)
    bins = cycles * np.arange(1, orders + 1)
    values = np.array([np.fft.rfft(audio[start:start + size] * window[:, None], axis=0)[bins] *
                       2 / window.sum() for start in starts])
    centers = starts + size / 2
    # Two-cycle Hann is orthogonal between integer orders; it equals the joint
    # weighted least-squares projection without needing a matrix inversion.
    at_reference = values[:, reference - 1] * np.exp(-2j * np.pi * reference * starts[:, None] / CYCLE)
    # An absent reference is rejected rather than replaced by neighbouring lines.
    power = abs(values[:, :, 0]) ** 2
    supported = power[:, reference - 1] >= np.maximum(power.max(axis=1), 1e-30) * .001
    return centers, at_reference, dict(supported=supported,
        reference_relative_power_db=10 * np.log10(np.maximum(power[:, reference - 1], 1e-30) /
                                                   np.maximum(power.max(axis=1), 1e-30)))


def diagnostics(audio, reference=5):
    result = {}
    for order in (3, 5, 7, 10, 15):
        _, values, quality = carrier_rows(audio, order)
        coherence = abs(values.mean(axis=0)) / np.maximum(np.mean(abs(values), axis=0), 1e-30)
        result[str(order)] = dict(fitted=order == reference, coherence_LR=coherence.tolist(),
            supported_fraction=float(quality['supported'].mean()))
    return result


def independent_agreement(values):
    """Two unfitted L carriers, each supported in >=80% windows, coherence>=.8.

    This rejects clear disagreement; it does not prove a physical engine clock.
    R is retained as an observation, never forced to match L.
    """
    accepted = [int(k) for k, row in values.items() if not row['fitted'] and
                row['supported_fraction'] >= .8 and row['coherence_LR'][0] >= .8]
    return dict(passed=len(accepted) >= 2, orders=accepted,
                rule='>=2 separate L carriers; support fraction>=.8 and phase coherence>=.8')


def polish(audio, source_start, normalized, positions, reference, cutoff):
    centers, rows, quality = carrier_rows(normalized, reference)
    if not quality['supported'].all():
        raise ValueError('Local reference is below -30dB of strongest observed harmonic')
    angle = np.unwrap(np.angle(rows[:, 0]))
    if np.max(abs(np.diff(angle))) > np.pi * .8:
        raise ValueError('Local carrier phase is not connected')
    correction = (angle - angle[0]) / (2 * np.pi * reference)
    indices = np.arange(int(centers[0]), int(centers[-1]) + 1)
    new_phase = indices / CYCLE + np.interp(indices, centers, correction)
    if np.min(np.diff(new_phase)) <= 0:
        raise ValueError('Local corrected phase is not monotonic')
    phase = np.arange(int(np.ceil(new_phase[0] * CYCLE)), int(np.floor(new_phase[-1] * CYCLE))) / CYCLE
    at = np.interp(phase, new_phase, indices)
    where = np.interp(at, np.arange(len(positions)), positions)
    roots = 1 / (CYCLE * np.diff(where))
    final_cutoff = min(cutoff, .38 * CYCLE * float(min(roots)))
    result = render_positions(audio, source_start, where, final_cutoff)
    measured = diagnostics(result, reference)
    evidence = dict(reference_order=reference, projection_cycles=2, reference_gate_orders=20,
        reference_channel='L; same coordinate applies to original L/R',
        minimum_reference_relative_db=float(min(quality['reference_relative_power_db'])),
        maximum_phase_step=float(max(abs(np.diff(angle)))), source_cutoff_hz=final_cutoff,
        source_seconds=[float(where[0]), float(where[-1])], inferred_root_hz_range=[float(min(roots)), float(max(roots))],
        diagnostics=measured, initial_diagnostics=diagnostics(normalized, reference),
        independent_agreement=independent_agreement(measured),
        edge_policy='Discard one unsupported cycle at each end; no phase extrapolation',
        warning='Reference-phase assumption; separate carrier agreement must be inspected')
    return result, where, evidence

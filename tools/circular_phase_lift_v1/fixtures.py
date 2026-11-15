"""Analytic branch, gauge and ambiguity controls, independent of recordings."""
import numpy as np
from .lift import lift_block


def principal(value):
    return np.remainder(value+np.pi, 2*np.pi)-np.pi


def stereo(common, relative, amplitude, carrier):
    angles = np.stack([common+relative/2, common-relative/2], axis=-1)
    z = amplitude*np.exp(1j*angles)
    return z, np.sum(amplitude*np.cos(carrier[..., None]+angles), axis=1)


def run():
    n = np.arange(4096)
    carrier = 2*np.pi*n[:, None]*np.array([12, 31, 47])[None]/len(n)
    common = np.zeros_like(carrier)
    amplitude = np.ones(carrier.shape+(2,))/3
    rows = {}
    paths = {}
    smooth = .31 + 2*np.pi*n[:, None]/len(n)*np.array([4, 6, 8])[None]
    for label, truth in [('positive_branch', smooth), ('negative_branch', -smooth)]:
        raw = principal(truth)
        lifted, state, extra = lift_block(raw)
        _, actual = stereo(common, lifted, amplitude, carrier)
        _, expected = stereo(common, truth, amplitude, carrier)
        spectrum = np.fft.rfft(actual, axis=0)/len(n)
        allowed = [{14, 34, 51}, {10, 28, 43}]
        if label == 'negative_branch':
            allowed.reverse()
        leak = []
        for channel in (0, 1):
            mask = np.ones(len(spectrum), bool)
            mask[list(allowed[channel])] = False
            leak.append(float(np.sum(abs(spectrum[mask, channel])**2)))
        rows[label] = dict(phase_error=float(abs(lifted-truth).max()),
                           wave_error=float(abs(actual-expected).max()),
                           off_analytic_bins_power=max(leak),
                           branch_increments=int(np.count_nonzero(extra['increments'])))
        paths[label] = dict(raw=raw, lifted=lifted, truth=truth, common=common,
                            amplitude=amplitude, carrier=carrier, audio=actual,
                            winding=extra['winding'])
    no_cross = .6*np.sin(n[:, None]*np.array([.01, .02, .03]))+np.array([0., 4., -7.])
    value, _, info = lift_block(no_cross)
    rows['no_crossing_exact'] = dict(bit_exact=bool(np.array_equal(value, no_cross)),
                                    zero_winding=bool(not info['winding'].any()))
    paths['no_crossing_exact'] = dict(raw=no_cross, lifted=value)
    raw = paths['positive_branch']['raw']
    lifted = paths['positive_branch']['lifted']
    winding = paths['positive_branch']['winding']
    zraw, audio_raw = stereo(common, raw, amplitude, carrier)
    zgauge, audio_gauge = stereo(common+np.pi*winding, lifted, amplitude, carrier)
    rows['gauge_compensation'] = dict(coefficient_error=float(abs(zgauge-zraw).max()),
                                      wave_error=float(abs(audio_gauge-audio_raw).max()))
    zlift, audio_lift = stereo(common, lifted, amplitude, carrier)
    rows['held_common_changes_wave'] = dict(wave_difference_RMS=float(np.sqrt(np.mean((audio_lift-audio_raw)**2))),
                                             circular_error=float(abs(np.exp(1j*lifted)-np.exp(1j*raw)).max()))
    varied = amplitude*(1+.2*np.sin(n[:, None, None]*np.array([.003, .005])[None, None]))
    z1, _ = stereo(common, raw, varied, carrier)
    z2, _ = stereo(common, lifted, varied, carrier)
    rows['instantaneous_stereo_invariants'] = dict(power_error=float(abs(abs(z1)**2-abs(z2)**2).max()),
        cross_error=float(abs(z1[..., 0]*z1[..., 1].conj()-z2[..., 0]*z2[..., 1].conj()).max()))
    fast = .2+n[:, None]*1.25*np.pi
    aliased = .2-n[:, None]*.75*np.pi
    observed = principal(fast)
    minimum_step, _, _ = lift_block(observed)
    tie = np.array([[0.], [np.pi], [0.], [-np.pi]])
    _, _, ties = lift_block(tie)
    rows['fast_motion_ambiguity'] = dict(circular_indistinguishability=float(abs(np.exp(1j*fast)-np.exp(1j*aliased)).max()),
        lift_differs_from_fast=bool(abs(minimum_step-fast).max()>100),
        aliased_phase_error=float(abs(minimum_step-aliased).max()),
        half_turn_steps_flagged=int(ties['half_turn_ambiguous'].sum()),
        physical_velocity_identified=False)
    paths['fast_motion_ambiguity'] = dict(raw=observed, lifted=minimum_step, truth=fast, alternative=aliased)
    for block in (37, 1024):
        state = None
        blocks = []
        for start in range(0, len(raw), block):
            result, state, _ = lift_block(raw[start:start+block], state)
            blocks.append(result)
        assert np.array_equal(np.concatenate(blocks), lifted)
        assert np.array_equal(state.winding, winding[-1])
    rows['block_continuity'] = dict(blocks=[37, 1024], output_bit_exact=True, terminal_state_exact=True)
    return rows, paths

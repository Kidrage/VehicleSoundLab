"""Extend an immutable target using observed source context, never fitted loops."""
import numpy as np
from exterior_clock_v1.warp import RATE, CYCLE, warp, polish, render_positions
from .observation import ContextRejected, corrected_grid


def extend(audio, source_start, clock_times, root_hz, aperture, original_audio,
           original_positions, cutoff, margin=2048, reference=5):
    audio = np.asarray(audio, float)
    clock_times, root_hz = np.asarray(clock_times, float), np.asarray(root_hz, float)
    if audio.ndim != 2 or audio.shape[1] != 2 or not np.isfinite(audio).all():
        raise ContextRejected('finite_stereo_recording_required')
    if (len(clock_times) < 2 or clock_times.shape != root_hz.shape or
            not np.isfinite(clock_times).all() or not np.isfinite(root_hz).all() or
            np.min(np.diff(clock_times)) <= 0 or np.min(root_hz) <= 0):
        raise ContextRejected('finite_positive_observed_clock_required')
    if margin != 2048 or reference != 5:
        raise ContextRejected('undeclared_context_or_reference')
    coarse, original_coarse_positions, initial = warp(
        audio, source_start, clock_times, root_hz, *aperture)
    pad = 4*CYCLE
    start = max(clock_times[0], source_start+.1)
    stop = min(clock_times[-1], source_start+len(audio)/RATE-.1-1/RATE)
    ticks = np.arange(int(np.ceil(start*RATE)), int(np.floor(stop*RATE))+1)
    times = ticks/RATE
    origin = round(aperture[0]*RATE)
    center = int(np.searchsorted(ticks, origin))
    if not 0 <= center < len(times) or ticks[center] != origin:
        raise ContextRejected('observed_clock_or_FIR_guard_missing')
    hz = np.interp(times, clock_times, root_hz)
    increments = (hz[:-1]+hz[1:])/(2*RATE)
    phase = np.empty(len(times))
    phase[center:] = np.r_[0., np.cumsum(increments[center:])]
    phase[:center] = -np.cumsum(increments[:center][::-1])[::-1]
    indices = np.arange(-pad, len(coarse)+pad)
    q = indices/CYCLE
    if not phase[0] <= q[0] < q[-1] <= phase[-1]:
        raise ContextRejected('complete_observed_outer_windows_missing')
    coarse_positions = np.interp(q, phase, times)
    if np.max(abs(coarse_positions[pad:pad+len(coarse)]-original_coarse_positions)) > 2e-12:
        raise ContextRejected('coarse_original_coordinates_changed')
    coarse_positions[pad:pad+len(coarse)] = original_coarse_positions
    outer = render_positions(audio, source_start, coarse_positions, initial['source_cutoff_hz'])
    if np.max(abs(outer[pad:pad+len(coarse)]-coarse)) > 2e-12:
        raise ContextRejected('coarse_original_audio_changed')
    outer[pad:pad+len(coarse)] = coarse
    measured = corrected_grid(outer, -pad, coarse, reference)
    # Check the original caller contract only after reference quality. Weak
    # references cannot obtain a fake phase by unwrapping floating-point noise.
    rebuilt, rebuilt_positions, old = polish(audio, source_start, coarse,
        original_coarse_positions, reference, initial['source_cutoff_hz'])
    if not np.array_equal(rebuilt_positions, original_positions):
        raise ContextRejected('original_corrected_coordinates_not_exact')
    if not np.array_equal(rebuilt, original_audio) or cutoff != old['source_cutoff_hz']:
        raise ContextRejected('original_corrected_audio_or_cutoff_not_exact')
    first = int(np.ceil(measured['phase'][np.searchsorted(measured['indices'], 2048)]*CYCLE))
    sample_indices = first+np.arange(-margin, len(original_positions)+margin)
    desired = sample_indices/CYCLE
    if not measured['phase'][0] <= desired[0] < desired[-1] <= measured['phase'][-1]:
        raise ContextRejected('corrected_outer_phase_not_observed')
    at = np.interp(desired, measured['phase'], measured['indices'])
    positions = np.interp(at, indices, coarse_positions)
    discrepancy = float(np.max(abs(positions[margin:-margin]-original_positions)))
    if discrepancy > 2e-12:
        raise ContextRejected('original_corrected_phase_join_changed')
    positions[margin:-margin] = original_positions
    if np.min(np.diff(positions)) <= 0:
        raise ContextRejected('nonmonotonic_final_coordinate')
    inferred = 1/(CYCLE*np.diff(positions))
    if cutoff > .45*CYCLE*np.min(inferred):
        raise ContextRejected('original_cutoff_exceeds_outer_antialias_budget')
    result = render_positions(audio, source_start, positions, cutoff)
    rerender_error = float(np.max(abs(result[margin:-margin]-original_audio)))
    if rerender_error > 2e-12:
        raise ContextRejected('original_render_join_changed')
    result[margin:-margin] = original_audio
    validation_indices = np.arange(int(np.ceil(measured['phase'][0]*CYCLE)),
                                   int(np.floor(measured['phase'][-1]*CYCLE)))
    validation_at = np.interp(validation_indices/CYCLE, measured['phase'], measured['indices'])
    validation_positions = np.interp(validation_at, indices, coarse_positions)
    validation_audio = render_positions(audio, source_start, validation_positions, cutoff)
    arrays = dict(audio=result, positions=positions, original_audio=original_audio,
        original_positions=original_positions, coarse_audio=outer,
        coarse_positions=coarse_positions, coarse_indices=indices,
        source_clock_times=times, source_clock_phase=phase,
        sample_indices=sample_indices, validation_indices=validation_indices,
        validation_positions=validation_positions, validation_audio=validation_audio,
        **{'observed_'+k:v for k,v in measured.items()})
    info = dict(original_frames=len(original_positions), extended_frames=len(result),
        margin_samples_each_side=margin, reference_order=reference, reference_channel='L/common stereo',
        coarse_padding_samples_each_side=pad, cutoff_hz=cutoff,
        minimum_reference_strength=float(np.min(measured['reference_strength'])),
        original_positions_bitwise_exact=True, original_audio_bitwise_exact=True,
        original_join_coordinate_error_seconds=discrepancy,
        original_join_rerender_error_FS=rerender_error,
        actual_source_seconds=[float(positions[0]),float(positions[-1])],
        complete_observation_source_seconds=[float(coarse_positions[0]),float(coarse_positions[-1])],
        inferred_acoustic_root_range_hz=[float(np.min(inferred)),float(np.max(inferred))],
        observed_phase_cycle_range=[float(measured['phase'][0]),float(measured['phase'][-1])],
        no_phase_extrapolation=True, no_physical_RPM_or_load_claim=True,
        no_runtime_or_sustained_voice_qualification=True)
    return arrays, info

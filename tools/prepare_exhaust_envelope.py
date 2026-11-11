"""Bounded reference-informed voicing proposal, never manifold identification."""
import json
from runtime_review import ROOT, sha
from reference_segments import read_segment
from spectral_coordinates import smooth_spectra, ShapeSettings
import numpy as np
import soundfile as sf
from scipy import signal, optimize

OUT = ROOT/'renders/exhaust_envelope_v1'
SOURCE = ROOT/'experiments/exhaust_envelope_v1'
CENTRES = np.array([1800., 3500., 6500.])
Q = .7


def coefficients(rate, hz, gain):
    a = 10**(gain/40)
    w = 2*np.pi*hz/rate
    alpha = np.sin(w)/(2*Q)
    return np.array([1+alpha*a, -2*np.cos(w), 1-alpha*a,
                     1+alpha/a, -2*np.cos(w), 1-alpha/a])


def response(frequency, gains, rate=48000):
    total = np.ones(len(frequency), dtype=complex)
    for hz, gain in zip(CENTRES, gains):
        c = coefficients(rate, hz, gain)
        _, h = signal.freqz(c[:3], c[3:], worN=frequency, fs=rate)
        total *= h
    return 20*np.log10(np.maximum(abs(total), 1e-30))


def main():
    if (OUT/'recipe.json').exists() or (SOURCE/'recipe.inc').exists():
        raise SystemExit('Preserve completed envelope recipe.')
    OUT.mkdir(parents=True, exist_ok=True)
    SOURCE.mkdir(parents=True, exist_ok=True)
    audio, rate, provenance = read_segment('A_exterior_blips', 'exterior_dynamic_observation')
    frequency, at, db = smooth_spectra(audio, rate)
    at += provenance['source_seconds'][0]
    selected = (at >= 238.18) & (at <= 238.52)
    # Both microphone channels contribute observations; never label them banks.
    target = db[selected].mean(axis=(0, 1))
    mask = (frequency >= 1500) & (frequency <= 8000)
    target = target[mask]-target[mask].mean()
    prior = json.loads((ROOT/'renders/exhaust_phase_v1/results.json').read_text())
    inputs = {}
    bases = {}
    for name in ['mid', 'high']:
        banks = []
        for bank in ['left', 'right']:
            path = ROOT/f'renders/exhaust_phase_v1/{name}_base_source_exhaust_{bank}.wav'
            assert sha(path) == prior['files'][path.name]
            inputs[str(path.relative_to(ROOT)).replace('\\', '/')] = sha(path)
            x, sr = sf.read(path)
            assert sr == rate
            banks.append(x)
        hz, time, shape = smooth_spectra(np.column_stack(banks), rate)
        assert np.array_equal(hz, frequency)
        use = (time >= 2.5) & (time <= 4.8)
        base = shape[use].mean(axis=(0, 1))[mask]
        bases[name] = base-base.mean()
    def residual(gains):
        curve = response(frequency[mask], gains)
        curve -= curve.mean()
        # Equal weighting of the two unmatched engineering RPM cases. The
        # small gain penalty favours a restrained diagnostic correction.
        return np.r_[np.concatenate([(base+curve-target)/np.sqrt(len(target)) for base in bases.values()]), .15*gains]
    fit = optimize.least_squares(residual, np.zeros(3), bounds=(-3., 3.),
                                 xtol=1e-12, ftol=1e-12, gtol=1e-12)
    gains = fit.x
    grid = np.geomspace(20, 23000, 4096)
    maximum = float(abs(response(grid, gains)).max())
    low = float(abs(response(grid[grid <= 400], gains)).max())
    # Re-evaluate after scaling: cascading peaking filters is not exactly
    # linear in dB gains away from their centres.
    scale = 1.
    for _ in range(100):
        final = gains*scale
        curve = response(grid, final)
        if abs(curve).max() <= 6 and abs(curve[grid <= 400]).max() <= .3:
            break
        scale *= .98
    else:
        raise AssertionError('Could not enforce correction bounds')
    score = {}
    for name, base in bases.items():
        score[name] = {}
        for tag, strength in [('base', 0.), ('half', .5), ('full', 1.)]:
            correction = response(frequency[mask], final*strength)
            correction -= correction.mean()
            score[name][tag] = float(np.sqrt(np.mean((base+correction-target)**2)))
    held_out = {}
    for name, limits in [('first_later', (238.70, 239.)), ('second', (241.22, 241.62))]:
        use = (at >= limits[0]) & (at <= limits[1])
        future = db[use].mean(axis=(0, 1))[mask]
        future -= future.mean()
        held_out[name] = dict(seconds=list(limits), scores={})
        for base_name, base in bases.items():
            held_out[name]['scores'][base_name] = {}
            for tag, strength in [('base', 0.), ('half', .5), ('full', 1.)]:
                correction = response(frequency[mask], final*strength)
                correction -= correction.mean()
                held_out[name]['scores'][base_name][tag] = float(np.sqrt(np.mean((base+correction-future)**2)))
    text = '/* Generated bounded diagnostic recipe; see renders/exhaust_envelope_v1/recipe.json. */\n'
    text += '\n'.join(f'{{{hz:.17g}, {Q:.17g}, {gain:.17g}}},' for hz, gain in zip(CENTRES, final))+'\n'
    (SOURCE/'recipe.inc').write_text(text, encoding='utf-8')
    result = dict(experiment='exhaust_envelope_v1', base_runtime='0.16.0', seed=48271,
        recipe=[dict(hz=float(hz), q=Q, gain_db=float(gain)) for hz, gain in zip(CENTRES, final)],
        strengths=dict(base=0., half=.5, full=1.), training_reference=provenance,
        selected_training_centres_seconds=[238.18, 238.52], evaluate_hz=[1500, 8000],
        inputs=inputs, source_analysis='2.5-4.8s steady 4000/8000 RPM exported exhaust objects; equal log-power geometric shape, no waveforms summed. Unmatched to reference RPM/load/microphone.',
        proposal='Three broad engineering peaking filters. Gain bounds +/-3dB each; cascade <=6dB; <=0.3dB below400Hz at48k. Fixed centres/Q are design choices, not identified car modes.',
        initial_maximum_db=maximum, initial_below400_maximum_db=low, applied_scale=scale,
        measured_proposal_maximum_db=float(abs(curve).max()),
        measured_proposal_below400_maximum_db=float(abs(curve[grid <= 400]).max()),
        optimizer=dict(success=bool(fit.success), cost=float(fit.cost), evaluations=fit.nfev),
        source_shape_proxy_scores=score, held_out_shape_proxy_scores=held_out,
        inference='Reference-informed bounded voicing only. Mixed recording versus source proxy and unmatched conditions cannot identify a physical transfer or predict perceived realism. Held-out values are diagnostics, not matching-state validation.',
        script_sha256=sha(__file__), spectral_tools_sha256=sha(ROOT/'tools/spectral_coordinates.py'),
        generated_profile_sha256=sha(SOURCE/'recipe.inc'))
    (OUT/'recipe.json').write_text(json.dumps(result, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps({k:result[k] for k in ['recipe','applied_scale','measured_proposal_maximum_db','measured_proposal_below400_maximum_db','source_shape_proxy_scores','held_out_shape_proxy_scores']}, indent=2))


if __name__ == '__main__':
    main()

"""Plan-driven offline local-voice extraction using the existing analysis/C seams."""
from fractions import Fraction
from pathlib import Path
import subprocess
import numpy as np
import soundfile as sf
from scipy import signal
from B_shift_voice_v1.selection import anchor, track
from decel_source_v1.aperture import extract
from decel_source_v1.checks import run as decreasing_controls
from drive_evidence_v1.sources import read
from exterior_clock_v1.warp import carrier_rows
from research_archive_v1 import save, sha
from shift_evidence_v1.spectrum import observe
from sound_dna.windowed import estimate
from sound_dna.profile import export
from .render import RAW_PROTOCOL, playback_argument


def controls(plan):
    decreasing = decreasing_controls(plan)
    rate = 48000
    times = np.arange(5 * rate) / rate
    roots = 64 * np.exp(.06 * times)
    cycles = np.r_[0., np.cumsum((roots[1:] + roots[:-1]) / (2 * rate))]
    audio = np.zeros((len(times), 2))
    for order, amplitude in ((3, .04), (5, .15), (7, .03), (10, .08), (15, .025)):
        for c in (0, 1):
            audio[:, c] += amplitude * (1 - .2 * c) * np.cos(2 * np.pi * order * cycles + .13 * order + .35 * c)
    grid = np.arange(.2, 4.801, .005)
    clock = [dict(seconds=float(t), root_hz=float(64 * np.exp(.06 * t) * 1.008)) for t in grid]
    increasing = []
    for center in (1.5, 3.5):
        normalized, where, info = extract(audio, 0, clock, center, plan)
        phase_error = float(np.std(np.interp(where, times, cycles) - np.arange(len(where)) / 1024))
        assert phase_error < plan['gates']['known_phase_cycle_std']
        assert min(v for values in info['heldout_coherence'].values() for v in values) > .99
        lr_error = 0.
        for order in (3, 5, 7, 10, 15):
            _, z = carrier_rows(normalized, order)
            delta = np.angle(np.exp(1j * (np.angle(z[:, 1] / z[:, 0]) - .35)))
            lr_error = max(lr_error, float(abs(delta).max()))
        assert lr_error < .002
        increasing.append(dict(center=center, phase_cycle_std=phase_error, LR_phase_error=lr_error, extraction=info))
    t = np.arange(2 * rate) / rate
    tone = sum(a * np.cos(2 * np.pi * 40 * k * t + .13 * k) for k, a in ((2, .02), (3, .03), (5, .2), (7, .025)))
    observed = observe(np.column_stack((tone, .8 * tone)), 0, 80)
    family = track(observed, anchor(observed, .05), dict(plan, source_seconds=[0, 2]))
    assert family['status'] == 'connected_observed_family'
    root_error = max(abs(v['root_hz'] - 40) for v in family['rows'])
    assert root_error < .1
    silent = observe(np.zeros((rate, 2)), 0, 80)
    missing = track(silent, anchor(silent, .05), dict(plan, source_seconds=[0, 1]))
    assert missing['status'] == 'no_anchor_peak'
    return dict(decreasing=decreasing, increasing=increasing, known_family_root_error=root_error,
                silent_status=missing['status'], generic_phase_qualification=False)


def fit_case(workspace, case, plan, folder, probe, repo):
    audio, provenance = read(workspace, case['segment'], case['use'])
    start = provenance['seconds'][0]
    assert start <= case['seconds'][0] < case['seconds'][1] <= provenance['seconds'][1]
    first, stop = [round((v - start) * 48000) for v in case['seconds']]
    native = audio[first:stop]
    folder.mkdir(exist_ok=False)
    sf.write(folder / 'native.wav', native, 48000, subtype='FLOAT')
    observed = observe(native, case['seconds'][0], plan['window_ms'], hop=plan['hop'])
    np.savez_compressed(folder / 'observed.npz', **observed)
    selected = anchor(observed, case['anchor_seconds'])
    family = track(observed, selected, dict(plan, source_seconds=case['seconds']))
    row = dict(case=case, provenance=provenance, anchor=selected, family=family, qualified=False, renders=[])
    save(folder / 'selection.json', row)
    if family['status'] != 'connected_observed_family':
        row.update(stage='family', reason='Declared local family unsupported; no alternate anchor/window/ref/gate')
        return row
    try:
        normalized, positions, info = extract(native, case['seconds'][0], family['rows'], case['center_seconds'], plan)
    except ValueError as exc:
        row.update(stage='aperture', reason=str(exc))
        return row
    sf.write(folder / 'normalized.wav', normalized, 48000, subtype='FLOAT')
    np.savez_compressed(folder / 'coordinates.npz', source_seconds=positions)
    observations = len(range(0, len(normalized) - 4096 + 1, 256))
    row.update(extraction=info, observations=observations)
    if observations < plan['gates']['minimum_observations'] or min(v for values in info['heldout_coherence'].values() for v in values) <= plan['gates']['heldout_carrier_coherence']:
        row.update(stage='heldout', reason='Original observations/heldout gate failed; no profile')
        return row
    model, statistics = estimate(normalized, plan['harmonics'], plan['components'])
    export(folder / 'voice.model', model, info['root_hz'])
    ratio = Fraction(46.875 / info['root_hz']).limit_denominator(10000)
    reference = signal.resample_poly(normalized, ratio.numerator, ratio.denominator, axis=0, window=('kaiser', 8.6))
    sf.write(folder / 'reference.wav', reference, 48000, subtype='FLOAT')
    playback = playback_argument(plan.get('render_protocol', RAW_PROTOCOL), info['root_hz'])
    for seed in plan['seeds']:
        argv = list(map(str, [probe, folder / 'voice.model', folder / ('DNA_%d.wav' % seed), plan['seconds'], playback, 1, seed, 512]))
        done = subprocess.run(argv, cwd=repo, capture_output=True, timeout=180)
        (folder / ('C_%d.log' % seed)).write_bytes(done.stdout + done.stderr)
        assert done.returncode == 0, (argv, done.returncode)
        wave, rate = sf.read(folder / ('DNA_%d.wav' % seed), always_2d=True)
        assert rate == 48000 and wave.shape == (plan['seconds'] * 48000, 2) and np.isfinite(wave).all()
        peak = float(abs(wave).max())
        assert peak * .5 < plan['gates']['output_peak_after_common_gain']
        row['renders'].append(dict(seed=seed, argv=argv, exit_code=done.returncode, peak_FS=peak,
                                   sha256=sha(folder / ('DNA_%d.wav' % seed))))
    row.update(qualified=True, stage='local_voice', statistics=statistics,
               resample_ratio=[ratio.numerator, ratio.denominator])
    return row

"""Known low/mid multiburst first, then fixed E full interval and legacy jobs."""
import argparse
from copy import deepcopy
from pathlib import Path
import shutil

import numpy as np
import soundfile as sf

from author_event import author
from event_authoring.audio import read
from event_authoring.contour_all_bands import fit, observations
from event_authoring.contour_joint import shape_errors
from event_authoring.contour_knots import propose
from event_authoring.measure import observe
from event_authoring.model import synth
from event_authoring.native import Renderer
from research_archive_v1 import load, save, sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    out = args.output
    out.mkdir(parents=True, exist_ok=False)
    repo = Path(__file__).resolve().parents[1]
    root = Path('E:/VehicleSoundLab/references/analysis')
    shutil.copy2(__file__, out/'executed_verification.py')
    report = dict(result='running', goal_complete=False, timbre_accepted=False)
    try:
        renderer = Renderer(repo)
        entry = deepcopy(load(root/'low_mid_event_scan_v1/C1/event-profile.json')['parameters'])
        entry.update(duration_seconds=.6, noise_lowpass_hz=0.)
        entry['modes'] = [dict(hz=hz, end_hz=hz, amplitude=amp, phase=phase,
                               decay_seconds=1., attack_seconds=0.)
                          for hz, amp, phase in [(180., .22, .3), (650., .12, 1.2)]]
        for band in entry['bands']:
            band.update(amplitude=0., attack_seconds=0., decay_seconds=1.)
        truth = deepcopy(entry)
        truth['contours'] = [dict(low_hz=lo, high_hz=hi,
            seconds=[0., .06, .14, .24, .34, .46, .6], gain=gain)
            for lo, hi, gain in [(60., 300., [.05, .3, 1., .08, .8, .4, .02]),
                                (300., 1200., [.03, .7, .5, .1, .9, .2, .01])]]
        t = np.arange(28800)/48000
        background = .004*np.sin(2*np.pi*3100*t)+.001*np.sin(2*np.pi*7300*t+.2)
        known = synth(truth, seconds=.6)+background
        original = np.column_stack((known, -known))
        noise = np.column_stack((background, -background))
        _, arrays = observe(original, noise)
        time, target, groups = observations(original, noise)
        assert [r['selected'] for r in groups] == [True, True, False, False], groups
        candidate, fitted, response = fit(entry, original, noise, arrays)
        assert fitted['qualified'] and response['qualified'], fitted
        assert [(c['low_hz'], c['high_hz']) for c in candidate['contours']] == [(60, 300), (300, 1200)]
        indices = [0, 1]
        old = shape_errors(entry, target, .6, indices)
        new = shape_errors(candidate, target, .6, indices)
        assert all(a < b*.7 for a, b in zip(new, old)), (old, new)
        actual, metadata = renderer.render(candidate, 'afterfire', dict(seconds=.8))
        python = synth(candidate, seconds=.8)
        python = np.pad(python, (0, len(actual)-len(python)))
        assert np.max(abs(actual-python)) < 3e-7
        scaled_time, scaled_target, scaled_groups = observations(original*.2, noise*.2)
        assert [r['selected'] for r in scaled_groups] == [r['selected'] for r in groups]
        for index in indices:
            assert np.array_equal(propose(time, target[index], .6),
                                  propose(scaled_time, scaled_target[index], .6))
        save(out/'known-profile.json', candidate)
        sf.write(out/'known-original.wav', original, 48000, subtype='FLOAT')
        sf.write(out/'known-C.wav', actual, 48000, subtype='FLOAT')
        report['known'] = dict(reliable_low_mid_only=True, shape_before=old, shape_after=new,
            actual_C_python_max_error_FS=float(np.max(abs(actual-python))), power_scale_knots_exact=True,
            fit=fitted, C=metadata)
        print('Known low/mid multiburst and actual C passed', flush=True)
        job = load(repo/'research/E_full_event_v1.job.json')
        for variant in ('original', 'candidate'):
            folder = out/variant
            folder.mkdir()
            value = deepcopy(job)
            if variant == 'original':
                value.update(schema='vsl.event-authoring-job/4', envelope_fit='band-attack-v1',
                             name='E 完整背景间隔 · 原单段包络')
            save(folder/'job.json', value)
            result = author(folder/'job.json', folder/'analysis')
            assert result.get('status') != 'analysis_only', result
            doc = load(folder/'analysis/profile.json')
            x, _, _ = read(job['source'], *job['seconds'])
            bg, _, _ = read(job['source'], *job['background_seconds'])
            _, reference, rows = observations(x, bg)
            selected = [i for i, r in enumerate(rows) if r['selected']]
            seeds = []
            for seed in (27431, 48271, 93931, 17389):
                pcm, native = renderer.render(doc['parameters'], 'afterfire', dict(seconds=.8, seed=seed))
                expected = synth(doc['parameters'], seconds=.8, seed=seed)
                expected = np.pad(expected, (0, len(pcm)-len(expected)))
                error = float(np.max(abs(pcm-expected)))
                assert error < 3e-7
                sf.write(folder/f'C-{seed}.wav', pcm, 48000, subtype='FLOAT')
                save(folder/f'C-{seed}.json', native)
                # Actual C curves include the same fixed finite source duration.
                from event_authoring.temporal_fit import band_curves
                _, power = band_curves(pcm[:len(x)])
                a = power[selected]/np.maximum(power[selected].mean(axis=1), 1e-30)[:, None]
                b = reference[selected]/np.maximum(reference[selected].mean(axis=1), 1e-30)[:, None]
                seeds.append(dict(seed=seed, C_python_max_error_FS=error,
                                  shape_rmse=np.sqrt(np.mean((a-b)**2, axis=1)).tolist()))
            report[variant] = dict(selected_band_indices=selected, groups=rows, seeds=seeds,
                                    fit=doc['fit'], parameters_path=str(folder/'analysis/profile.json'))
            print('E', variant, 'four actual C seeds passed', flush=True)
        assert report['candidate']['selected_band_indices'] == report['original']['selected_band_indices']
        for old, new in zip(report['original']['seeds'], report['candidate']['seeds']):
            assert all(a <= b+1e-5 for a, b in zip(new['shape_rmse'], old['shape_rmse'])), (old, new)
        legacy = []
        for key in ('A', 'B'):
            original = load(root/f'event_knots_v1/verification1/{key}/analysis/profile.json')
            folder = out/('legacy-'+key)
            folder.mkdir()
            save(folder/'job.json', original['source_job'])
            author(folder/'job.json', folder/'analysis')
            assert load(folder/'analysis/profile.json')['parameters'] == original['parameters']
            legacy.append(dict(key=key, method='band-contour-v3', parameters_exact=True))
            print('Legacy', key, 'parameters exact', flush=True)
        binding = load(root/'event_full_envelope_v1/before/runtime.json')
        assert len(binding) == 459 and all(sha(repo/name) == digest for name, digest in binding.items())
        report.update(result='passed', legacy=legacy, runtime_voice_files_unchanged=459,
                      author_bridge_sha256=renderer.identity)
    except Exception as error:
        report.update(result='failed', error=repr(error))
        raise
    finally:
        save(out/'report.json', report)
    print(dict(result='passed'), flush=True)


if __name__ == '__main__':
    main()

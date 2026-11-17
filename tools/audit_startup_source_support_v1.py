"""Independently audit saved C audio; never fit, render or choose parameters."""
import argparse
from copy import deepcopy
from pathlib import Path
import shutil

import numpy as np
import soundfile as sf

from audit_startup_contour_ensemble_v1 import EDGES, powers
from research_archive_v1 import load, save, sha


def fixed_fields(profile):
    result = deepcopy(profile)
    for name in ('bands', 'contours', 'noise_lowpass_hz'):
        result.pop(name, None)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, args.output/Path(__file__).name)
    shutil.copy2(Path(__file__).with_name('audit_startup_contour_ensemble_v1.py'),
                 args.output/'independent_fft_helper.py')
    report_path = args.input/'report.json'
    report = load(report_path)
    assert report['result'] == 'passed' and report['qualified_cases'] == []
    rows, bindings, disagreements = [], {}, []
    for case in report['cases']:
        folder = args.input/case['kind']
        original = load(folder/'original-event-profile.json')['parameters']
        candidate_path = folder/'candidate-parameters-before-validation.json'
        candidate = load(candidate_path)
        assert sha(candidate_path) == case['candidate_parameters_sha256']
        assert sha(Path(case['document'])) == case['document_sha256']
        assert load(Path(case['document']))['parameters'] == original
        assert fixed_fields(original) == fixed_fields(candidate)
        assert 'noise_lowpass_hz' not in candidate
        assert len(candidate['bands']) == len(original['bands']) == 4
        assert len(candidate['contours']) == 4
        for old, new in zip(original['bands'], candidate['bands']):
            assert {k: v for k, v in old.items() if k not in ('hz', 'q', 'amplitude')} == {
                k: v for k, v in new.items() if k not in ('hz', 'q', 'amplitude')}
            assert 2 <= new['q'] <= 12 and 0 <= new['amplitude'] <= 8
        for contour in candidate['contours']:
            assert len(contour['seconds']) == len(contour['gain']) == 8
            assert np.all(np.diff(contour['seconds']) > 0)
            assert all(0 <= gain <= 8 for gain in contour['gain'])
        def read_source(binding):
            path = Path(binding['path'])
            assert sha(path) == binding['sha256']
            with sf.SoundFile(path) as stream:
                assert stream.samplerate == 48000
                stream.seek(binding['first_frame'])
                return stream.read(binding['last_frame']-binding['first_frame'],
                                   dtype='float64', always_2d=True)
        source, background = read_source(case['source']), read_source(case['background'])
        assert len(source) == case['observation_frames']
        # Positive excess is clipped per FFT bin, before band summation.
        frequency = np.fft.rfftfreq(2048, 1/48000)
        window = .5-.5*np.cos(2*np.pi*np.arange(2048)/2048)
        weights = np.full(1025, 2/(2048*(window@window)))
        weights[[0, -1]] *= .5
        def psd(wave):
            starts = np.arange(0, len(wave)-2048+1, 1024)
            offsets = starts[:, None]+np.arange(2048)[None, :]
            z = np.fft.rfft(wave[offsets]*window[None, :, None], axis=1)
            return (z.real**2+z.imag**2).mean(axis=(0, 2))*weights
        excess = np.maximum(psd(source)-psd(background), 0)
        target = np.array([excess[(frequency >= lo)&(frequency < hi)].sum()
                           for lo, hi in EDGES])
        curve = np.maximum(powers(source, 240)[1:5]-
                           powers(background, 240)[1:5].mean(axis=1)[:, None], 0)
        reference = curve/np.maximum(curve.mean(axis=1), 1e-30)[:, None]
        indices = [i for i, band in enumerate(case['bands']) if band['selected']]
        fitting = case['fitting']
        seeds = fitting['training_seeds']+fitting['held_out_seeds']
        assert len(set(seeds)) == 8
        assert [row['seed'] for row in case['native']] == seeds
        seed_checks = []
        for native in case['native']:
            measured = {}
            for label in ('old', 'candidate'):
                path = folder/(label+'-'+str(native['seed'])+'.wav')
                wave, rate = sf.read(path, dtype='float64')
                assert rate == 48000 and wave.ndim == 1 and len(wave) >= len(source)
                assert np.isfinite(wave).all()
                bindings[str(path)] = sha(path)
                peak = float(np.max(abs(wave)))
                assert peak == native[label]['peak']
                wave = wave[:len(source)]
                energy = powers(wave, 1024).mean(axis=1)
                significant = target >= float(target.sum())*1e-4
                db = 10*np.log10(np.maximum(energy, 1e-30)/np.maximum(target, 1e-30))
                passed = np.where(significant, abs(db) <= 3,
                                  energy <= np.maximum(2*target, float(target.sum())*2e-4))
                curve = powers(wave, 240)[1:5]
                normalized = curve/np.maximum(curve.mean(axis=1), 1e-30)[:, None]
                errors = np.sqrt(np.mean((normalized-reference)**2, axis=1))
                expected = np.array([b['error_db'] for b in native[label]['bands']])
                np.testing.assert_allclose(db, expected, atol=1e-11, rtol=1e-12)
                np.testing.assert_allclose(errors, native[label]['shape_rmse'], atol=1e-12, rtol=1e-12)
                assert passed.tolist() == [b['passed'] for b in native[label]['bands']]
                disagreements.append(float(np.max(abs(db-expected))))
                measured[label] = dict(spectral_pass=bool(passed.all()),
                    shape_rmse=errors.tolist(), peak_FS=peak)
            temporal = all(measured['candidate']['shape_rmse'][i] <=
                           measured['old']['shape_rmse'][i]+1e-10 for i in indices)
            qualified = bool(temporal and measured['candidate']['spectral_pass'])
            assert qualified == native['candidate']['qualified']
            seed_checks.append(dict(seed=native['seed'], **measured,
                                    temporal_nonregression=temporal, qualified=qualified))
        assert not fitting['useful'] and fitting['relative_legacy_shape_improvement'] < 0
        assert not fitting['qualified'] and not case['eligible_for_optional_authoring']
        assert not case['adopted']
        rows.append(dict(kind=case['kind'], seeds=seed_checks, eligible=False,
            modes_global_envelope_and_band_envelopes_unchanged=True,
            permitted_changes_only=True, candidate_parameters_sha256=sha(candidate_path)))
    repo = Path(__file__).resolve().parents[1]
    runtime = load(Path('E:/VehicleSoundLab/references/analysis/A_exterior_startup_v1/selection1/runtime.json'))
    assert len(runtime) == 459 and all(sha(repo/name) == digest for name, digest in runtime.items())
    assert len(bindings) == 32
    save(args.output/'report.json', dict(result='passed', reviewed_report=str(report_path),
        reviewed_report_sha256=sha(report_path), cases=rows, qualified_cases=[],
        waveforms=bindings, max_spectral_db_disagreement=max(disagreements),
        original_runtime_files_unchanged=459, no_fit_render_or_selection_performed=True,
        no_candidate_promoted=True, goal_complete=False, timbre_accepted=False))
    print('32 saved C waveforms independently checked; both support candidates remain refused', flush=True)


if __name__ == '__main__':
    main()

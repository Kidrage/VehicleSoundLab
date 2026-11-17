"""Read saved audio independently; do not fit, render or select a candidate."""
import argparse
from copy import deepcopy
from pathlib import Path
import shutil

import numpy as np
import soundfile as sf

from audit_startup_contour_ensemble_v1 import EDGES, powers
from research_archive_v1 import load, save, sha


def without_gains(profile):
    value = deepcopy(profile)
    for band in value['bands']:
        band.pop('gain')
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, args.output/Path(__file__).name)
    shutil.copy2(Path(__file__).with_name('audit_startup_contour_ensemble_v1.py'),
                 args.output/'independent_fft_helper.py')
    report = load(args.input/'report.json')
    assert report['result'] == 'passed' and report['qualified_cases'] == []
    window = .5-.5*np.cos(2*np.pi*np.arange(2048)/2048)
    frequency = np.fft.rfftfreq(2048, 1/48000)
    weights = np.full(1025, 2/(2048*(window@window)))
    weights[[0, -1]] *= .5
    def psd(wave):
        starts = np.arange(0, len(wave)-2048+1, 1024)
        z = np.fft.rfft(wave[starts[:, None]+np.arange(2048)[None, :]]*window[None, :, None], axis=1)
        return (z.real**2+z.imag**2).mean(axis=(0, 2))*weights
    def source(binding):
        assert sha(Path(binding['path'])) == binding['sha256']
        with sf.SoundFile(binding['path']) as stream:
            stream.seek(binding['first_frame'])
            return stream.read(binding['last_frame']-binding['first_frame'], dtype='float64', always_2d=True)
    rows, bindings, db_errors, shape_errors = [], {}, [], []
    for case in report['cases']:
        kind = case['kind']
        folder = args.input/kind
        original = load(folder/'original-event-profile.json')['parameters']
        fixed = deepcopy(original)
        fixed['bands'] = []
        fixed.pop('noise_lowpass_hz', None)
        candidate = load(folder/'candidate-before-validation.json')
        assert candidate['modal'] == fixed
        assert sha(folder/'candidate-before-validation.json') == case['candidate_parameters_sha256']
        assert without_gains(candidate) == without_gains(load(folder/'designed-profile.json'))
        x, bg = source(case['source']), source(case['background'])
        excess = np.maximum(psd(x)-psd(bg), 0)
        targets = np.array([excess[(frequency >= lo)&(frequency < hi)].sum() for lo, hi in EDGES])
        curve = np.maximum(powers(x, 240)[1:5]-powers(bg, 240)[1:5].mean(axis=1)[:, None], 0)
        reference = curve/curve.mean(axis=1)[:, None]
        significant = targets >= targets.sum()*1e-4
        checks = []
        for seed_row in case['seeds']:
            data = {}
            for label, key in [('old_C', 'old'), ('candidate_Python', 'candidate')]:
                path = folder/(label+'-'+str(seed_row['seed'])+'.wav')
                wave, rate = sf.read(path, dtype='float64')
                assert rate == 48000 and wave.ndim == 1 and np.isfinite(wave).all()
                bindings[str(path)] = sha(path)
                observation = wave[:len(x)]
                energy = powers(observation, 1024).mean(axis=1)
                db = 10*np.log10(np.maximum(energy, 1e-30)/np.maximum(targets, 1e-30))
                passed = np.where(significant, abs(db) <= 3,
                    energy <= np.maximum(2*targets, targets.sum()*2e-4))
                curve = powers(observation, 240)[1:5]
                error = np.sqrt(np.mean((curve/curve.mean(axis=1)[:, None]-reference)**2, axis=1))
                expected_db = np.array([b['error_db'] for b in seed_row[key]['bands']])
                expected_shape = np.array(seed_row[key]['shape_rmse'])
                # Prototype reports measured float64 before FLOAT-WAV storage.
                # Gates are recalculated without tolerance; only numeric-report
                # agreement allows the known FP32 storage quantization.
                np.testing.assert_allclose(db, expected_db, atol=3e-5, rtol=1e-7)
                np.testing.assert_allclose(error, expected_shape, atol=1e-6, rtol=1e-7)
                db_errors.append(float(np.max(abs(db-expected_db))))
                shape_errors.append(float(np.max(abs(error-expected_shape))))
                data[key] = dict(spectral_pass=bool(passed.all()), shape_rmse=error.tolist())
            temporal = bool(np.all(np.asarray(data['candidate']['shape_rmse']) <=
                                  np.asarray(data['old']['shape_rmse'])+1e-10))
            qualified = temporal and data['candidate']['spectral_pass']
            assert qualified == seed_row['candidate']['qualified']
            checks.append(dict(seed=seed_row['seed'], split=seed_row['split'], **data,
                               temporal_nonregression=temporal, qualified=qualified))
        assert not all(c['qualified'] for c in checks)
        assert not case['eligible_for_C_prototype'] and not case['adopted']
        rows.append(dict(kind=kind, checks=checks, eligible=False,
                         modal_and_filter_parameters_unchanged=True))
    repo = Path(__file__).resolve().parents[1]
    runtime = load(Path('E:/VehicleSoundLab/references/analysis/A_exterior_startup_v1/selection1/runtime.json'))
    assert len(bindings) == 32 and len(runtime) == 459
    assert all(sha(repo/name) == digest for name, digest in runtime.items())
    save(args.output/'report.json', dict(result='passed', reviewed_report=str(args.input/'report.json'),
        reviewed_report_sha256=sha(args.input/'report.json'), cases=rows, waveforms=bindings,
        max_spectral_db_disagreement=max(db_errors), max_shape_rmse_disagreement=max(shape_errors),
        FP32_storage_tolerance_only=True, qualification_gates_unchanged=True,
        qualified_cases=[], runtime_voice_files_unchanged=459,
        no_fit_render_or_selection_performed=True, goal_complete=False, timbre_accepted=False))
    print('32 saved waveforms audited; both candidates remain refused', flush=True)


if __name__ == '__main__':
    main()

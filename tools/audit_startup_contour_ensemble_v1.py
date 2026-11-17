"""Independent saved-C-audio audit; no solver or response-Gram imports."""
import argparse
from copy import deepcopy
from pathlib import Path
import shutil

import numpy as np
import soundfile as sf

from research_archive_v1 import load, save, sha

EDGES = ((0, 60), (60, 300), (300, 1200), (1200, 4500), (4500, 14000), (14000, 24001))


def powers(wave, hop):
    wave = np.asarray(wave, dtype=np.float64)
    if wave.ndim == 1:
        wave = wave[:, None]
    window = .5-.5*np.cos(2*np.pi*np.arange(2048)/2048)
    starts = np.arange(0, len(wave)-2048+1, hop)
    frequency = np.fft.rfftfreq(2048, 1/48000)
    weight = np.full(1025, 2/(2048*(window@window)))
    weight[[0, -1]] *= .5
    result = np.empty((6, len(starts)))
    for first in range(0, len(starts), 16):
        offsets = starts[first:first+16, None]+np.arange(2048)[None, :]
        z = np.fft.rfft(wave[offsets]*window[None, :, None], axis=1)
        energy = (z.real**2+z.imag**2).mean(axis=-1)*weight[None, :]
        for index, (low, high) in enumerate(EDGES):
            result[index, first:first+len(offsets)] = energy[:, (frequency >= low)&(frequency < high)].sum(axis=1)
    return result


def without_gains(profile):
    result = deepcopy(profile)
    for row in result['contours']:
        row.pop('gain')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    out = args.output
    out.mkdir(parents=True, exist_ok=False)
    shutil.copy2(Path(__file__), out/Path(__file__).name)
    repo = Path(__file__).resolve().parents[1]
    original_report = load(args.input/'report.json')
    assert original_report['result'] == 'passed'
    rows, all_errors, qualified = [], [], []
    for case in original_report['cases']:
        kind = case['kind']
        folder = args.input/kind
        original_doc = load(folder/'original-event-profile.json')
        original = original_doc['parameters']
        candidate = load(folder/'candidate-parameters-before-validation.json')
        assert sha(folder/'candidate-parameters-before-validation.json') == case['candidate_parameters_sha256']
        assert sha(Path(case['document'])) == case['document_sha256']
        assert without_gains(original) == without_gains(candidate)
        assert all(0 <= g <= 8 for c in candidate['contours'] for g in c['gain'])
        source = case['source']
        background = case['background']
        assert sha(Path(source['path'])) == source['sha256']
        def read_source(binding):
            with sf.SoundFile(binding['path']) as f:
                f.seek(binding['first_frame'])
                return f.read(binding['last_frame']-binding['first_frame'], dtype='float64', always_2d=True)
        x = read_source(source)
        bg = read_source(background)
        assert len(x) == case['observation_frames']
        f = np.fft.rfftfreq(2048, 1/48000)
        window = .5-.5*np.cos(2*np.pi*np.arange(2048)/2048)
        weight = np.full(1025, 2/(2048*(window@window)))
        weight[[0, -1]] *= .5
        def spectrum(wave):
            starts = np.arange(0, len(wave)-2048+1, 1024)
            offsets = starts[:, None]+np.arange(2048)[None, :]
            z = np.fft.rfft(wave[offsets]*window[None, :, None], axis=1)
            return (z.real**2+z.imag**2).mean(axis=(0, 2))*weight
        excess = np.maximum(spectrum(x)-spectrum(bg), 0)
        targets = np.array([excess[(f >= lo)&(f < hi)].sum() for lo, hi in EDGES])
        raw_curve = powers(x, 240)[1:5]
        target_curve = np.maximum(raw_curve-powers(bg, 240)[1:5].mean(axis=-1)[:, None], 0)
        reference = target_curve/np.maximum(target_curve.mean(axis=-1), 1e-30)[:, None]
        indices = [i for i, b in enumerate(case['bands']) if b['selected']]
        seed_checks = []
        for native in case['native']:
            seed = native['seed']
            data = {}
            for label in ('old', 'candidate'):
                wave, rate = sf.read(folder/(label+'-'+str(seed)+'.wav'), dtype='float64')
                assert rate == 48000 and wave.ndim == 1
                wave = wave[:len(x)]
                energy = powers(wave, 1024).mean(axis=1)
                total = float(targets.sum())
                significant = targets >= total*1e-4
                db = 10*np.log10(np.maximum(energy, 1e-30)/np.maximum(targets, 1e-30))
                passed = np.where(significant, abs(db) <= 3, energy <= np.maximum(2*targets, total*2e-4))
                curve = powers(wave, 240)[1:5]
                normalized = curve/np.maximum(curve.mean(axis=-1), 1e-30)[:, None]
                errors = np.sqrt(np.mean((normalized-reference)**2, axis=-1))
                np.testing.assert_allclose(errors, native[label]['shape_rmse'], atol=1e-12, rtol=1e-12)
                expected_db = np.array([b['error_db'] for b in native[label]['bands']])
                np.testing.assert_allclose(db, expected_db, atol=1e-11, rtol=1e-12)
                all_errors.append(float(np.max(abs(db-expected_db))))
                data[label] = dict(spectral_pass=bool(passed.all()), shape_rmse=errors.tolist())
            temporal = all(data['candidate']['shape_rmse'][i] <= data['old']['shape_rmse'][i]+1e-10 for i in indices)
            accepted = bool(data['candidate']['spectral_pass'] and temporal)
            assert accepted == native['candidate']['qualified']
            seed_checks.append(dict(seed=seed, **data, temporal_nonregression=temporal, qualified=accepted))
        useful = case['fitting']['useful']
        eligible = bool(useful and case['fitting']['qualified'] and all(s['qualified'] for s in seed_checks))
        assert eligible == case['eligible_for_optional_authoring']
        if eligible:
            qualified.append(kind)
        rows.append(dict(kind=kind, original_profile_untouched=True, only_existing_gains_changed=True,
                         seeds=seed_checks, eligible=eligible))
    assert qualified == original_report['qualified_cases'] == []
    bindings = load(Path('E:/VehicleSoundLab/references/analysis/A_exterior_startup_v1/selection1/runtime.json'))
    assert len(bindings) == 459 and all(sha(repo/name) == digest for name, digest in bindings.items())
    save(out/'report.json', dict(result='passed', reviewed_report=str(args.input/'report.json'),
        reviewed_report_sha256=sha(args.input/'report.json'), cases=rows, qualified_cases=qualified,
        max_spectral_db_disagreement=max(all_errors), original_runtime_files_unchanged=459,
        no_fit_or_selection_performed=True, no_candidate_promoted=True,
        goal_complete=False, timbre_accepted=False))
    print('32 saved C waveforms independently checked; both candidates remain refused', flush=True)


if __name__ == '__main__':
    main()

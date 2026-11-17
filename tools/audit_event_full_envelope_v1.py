"""Original master frames and independent FFT gates for the full E candidate."""
import argparse
from pathlib import Path
import shutil

import numpy as np
import soundfile as sf

from audit_startup_contour_v1 import spectral_power
from audit_startup_shape_v1 import EDGES, powers
from event_authoring.temporal_fit import band_curves
from research_archive_v1 import load, save, sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verification', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    repo = Path(__file__).resolve().parents[1]
    for name in ('audit_event_full_envelope_v1.py', 'audit_startup_contour_v1.py', 'audit_startup_shape_v1.py'):
        shutil.copy2(repo/'tools'/name, args.output/name)
    report = dict(result='running', goal_complete=False, timbre_accepted=False, physical_identity_confirmed=False)
    try:
        job = load(repo/'research/E_full_event_v1.job.json')
        source = Path(job['source'])
        assert sha(source) == '3db9ceac1fc00d27a8ceb7abda88c3efa78efad2b11d4b9d2664ae287cb0f9bf'
        with sf.SoundFile(source) as stream:
            assert stream.samplerate == 48000 and stream.channels == 2
            stream.seek(681120)
            raw = stream.read(14880, dtype='float64', always_2d=True)
            stream.seek(671520)
            bg = stream.read(9600, dtype='float64', always_2d=True)
            stream.seek(696000)
            following = stream.read(9600, dtype='float64', always_2d=True)
        independent_power = lambda x: sum(float(x[:, c] @ x[:, c]) for c in range(2))/(2*len(x))
        contrasts = [float(10*np.log10(independent_power(raw)/independent_power(b))) for b in (bg, following)]
        assert min(contrasts) >= 3
        time, original_curves = powers(raw)
        _, bg_curves = powers(bg)
        target = np.maximum(original_curves-bg_curves.mean(axis=1)[:, None], 0)
        production_time, production = band_curves(raw)
        np.testing.assert_allclose(production_time, time, rtol=0, atol=1e-15)
        np.testing.assert_allclose(production, original_curves[1:5], rtol=2e-12, atol=2e-15)
        frequency, raw_psd = spectral_power(raw)
        _, bg_psd = spectral_power(bg)
        excess = np.maximum(raw_psd-bg_psd, 0)
        delta = 48000/2048
        reference = np.array([excess[(frequency >= lo) & (frequency < hi)].sum()*delta for lo, hi in EDGES])
        documents = {}
        results = []
        for variant in ('original', 'candidate'):
            folder = args.verification/variant
            document = load(folder/'analysis/profile.json')
            documents[variant] = document
            copied, rate = sf.read(folder/'analysis/reference.wav', dtype='float64', always_2d=True)
            assert rate == 48000 and np.array_equal(raw, copied)
            reported = document['fit']['source_response_fit']['bands']
            np.testing.assert_allclose([r['target_power'] for r in reported], reference, rtol=2e-12, atol=1e-15)
            for seed in (27431, 48271, 93931, 17389):
                wave, rate = sf.read(folder/f'C-{seed}.wav', dtype='float64')
                assert rate == 48000 and np.all(wave[14880:] == 0)
                _, curve = powers(wave[:14880])
                _, spectrum = spectral_power(wave[:14880])
                bands = []
                for (lo, hi), amount in zip(EDGES, reference):
                    generated = float(spectrum[(frequency >= lo) & (frequency < hi)].sum()*delta)
                    error = float(10*np.log10(max(generated, 1e-30)/max(amount, 1e-30)))
                    significant = amount >= reference.sum()*1e-4
                    passed = abs(error) <= 3 if significant else generated <= max(amount*2, reference.sum()*2e-4)
                    bands.append(dict(hz=[lo, hi], target_power=float(amount), generated_power=generated,
                                      error_db=error, significant=bool(significant), passed=bool(passed)))
                assert all(row['passed'] for row in bands), (variant, seed, bands)
                normalized = curve[1:5]/np.maximum(curve[1:5].mean(axis=1), 1e-30)[:, None]
                expected = target[1:5]/np.maximum(target[1:5].mean(axis=1), 1e-30)[:, None]
                errors = np.sqrt(np.mean((normalized-expected)**2, axis=1)).tolist()
                results.append(dict(variant=variant, seed=seed, original_six_spectral_gates=bands,
                                    four_band_normalized_shape_rmse=errors, tail_exact_zero=True,
                                    peak=float(np.max(abs(wave))), wav_sha256=sha(folder/f'C-{seed}.wav')))
        selected = [k for k, r in enumerate(documents['candidate']['fit']['contour_fit']['bands']) if r['selected']]
        assert selected and 0 in selected
        for seed in (27431, 48271, 93931, 17389):
            old = next(r for r in results if r['seed'] == seed and r['variant'] == 'original')
            new = next(r for r in results if r['seed'] == seed and r['variant'] == 'candidate')
            assert all(new['four_band_normalized_shape_rmse'][i] <=
                       old['four_band_normalized_shape_rmse'][i]+1e-5 for i in selected)
        np.savez(args.output/'curves.npz', time=time, recorded=original_curves,
                 background=bg_curves.mean(axis=1), target=target)
        binding = load(args.verification.parent/'before/runtime.json')
        assert len(binding) == 459 and all(sha(repo/name) == digest for name, digest in binding.items())
        report.update(result='passed', original_frames=[681120, 696000], original_reference_exact=True,
            fixed_backgrounds_preserved=True, contrast_db=contrasts, selected_band_indices=selected,
            original_six_spectral_gates_all_eight=True, actual_C_selected_curves_nonregressing=True,
            results=results, runtime_voice_files_unchanged=459,
            method='Independent explicit periodic-Hann rFFT/PSD per channel, six spectral gates and240-frame time curves; original master sample ranges and dot-product contrasts.')
    except Exception as error:
        report.update(result='failed', error=repr(error))
        raise
    finally:
        save(args.output/'report.json', report)
    print(dict(result='passed', actual_C_cases=8, selected_bands=selected, contrast_db=contrasts), flush=True)


if __name__ == '__main__':
    main()

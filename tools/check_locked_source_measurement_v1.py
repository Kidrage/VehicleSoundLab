"""Known all-bin direct DFT and seventeen-score controls, before real use."""
import argparse
import math
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import save, sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'out'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[name] = '2'
    sys.path.insert(0, str(args.workspace/'tools/python_deps'))
    import numpy as np
    from locked_source_guard_v1.measurement import frame, declared, compare, fidelity
    repo = Path(__file__).resolve().parents[1]
    args.out.mkdir(parents=True, exist_ok=False)
    report = dict(result='running', cases=[], sources={})
    try:
        for path in [Path(__file__), *sorted((repo/'tools/locked_source_guard_v1').glob('*.py'))]:
            relative = path.relative_to(repo).as_posix()
            dest = args.out/'exact_sources'/relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)
            report['sources'][relative] = sha(dest)
        rng = np.random.default_rng(640288)
        for size in (16, 32, 4096):
            hop = 256 if size == 4096 else size//4
            count = size+257 if size == 4096 else 2*size+3
            audio = rng.normal(0, .02, (count, 2))
            audio[:, 0] += .03+.017*(-1.)**np.arange(count)
            audio[:, 1] += .5*np.roll(audio[:, 0], 3)
            rows, cover = frame(audio, size=size, hop=hop)
            starts = list(range(-(size-hop), count, hop))
            window = .5-.5*np.cos(2*np.pi*np.arange(size)/size)
            independent_cover = np.array([math.fsum(float(window[n-s]**2)
                for s in starts if 0 <= n-s < size) for n in range(count)])
            cover_error = float(np.max(abs(cover-independent_cover)))
            assert cover_error < 2e-12
            selected = [starts.index(s) for s in (0, 256)] if size == 4096 else range(len(starts))
            error = 0.
            for index in selected:
                start = starts[index]
                samples = np.zeros((size, 2))
                for n in range(size):
                    if 0 <= start+n < count:
                        samples[n] = audio[start+n]/math.sqrt(independent_cover[start+n])*window[n]
                expected = np.empty((size//2+1, 2), complex)
                for first in range(0, size//2+1, 128):
                    bins = np.arange(first, min(first+128, size//2+1))
                    ids = bins[:, None]*np.arange(size)[None, :] % size
                    angles = ids.astype(np.longdouble)*(2*np.arccos(np.longdouble(-1))/size)
                    table = np.cos(angles).astype(float)-1j*np.sin(angles).astype(float)
                    expected[first:first+len(bins)] = table@samples
                endpoint = np.full(size//2+1, np.sqrt(2.))
                endpoint[[0, -1]] = 1.
                expected *= endpoint[:, None]/math.sqrt(size)
                error = max(error, float(np.max(abs(rows[index]-expected))))
            assert error < 2e-12, (size, error)
            report['cases'].append(dict(size=size, frames=count, all_bins=size//2+1,
                windows_checked=len(selected), all_boundary_windows_checked=size != 4096,
                maximum_direct_DFT_error_FS=error, maximum_coverage_error=cover_error))
            print('SAVED_WAVE_DFT', size, error, flush=True)
        audio = rng.normal(0, .03, (9001, 2))
        weights = np.exp(np.linspace(-1., 1., 2049))
        gain = .017
        scored = declared(audio, (1+gain)*audio, 1.79, weights)
        expected = {key: [gain]*len(value) if isinstance(value, list) else gain for key, value in scored.items()}
        comparison = compare(scored, expected, enforce=True)
        assert fidelity(scored)
        zeros = np.zeros_like(audio)
        zero = declared(zeros, zeros, 1., np.ones(2049))
        assert all(v == 0 for value in zero.values() for v in (value if isinstance(value, list) else [value]))
        bad = declared(zeros, np.ones_like(zeros)*.01, 1., np.ones(2049))
        assert bad['target_wave_NRMSE'] is None and not fidelity(bad)
        rejected = []
        for label, kwargs in (
            ('missing_bin', dict(weights=weights[:-1])), ('zero_amplitude', dict(amplitude=0.)),
            ('complex_wave', dict(wave=audio.astype(complex))),
            ('nonfinite_wave', dict(wave=audio*np.nan)), ('short_wave', dict(wave=audio[:-1]))):
            values = dict(audio=audio, wave=audio, amplitude=1., weights=weights)
            values.update(kwargs)
            try:
                declared(**values)
            except ValueError:
                rejected.append(label)
            else:
                raise AssertionError('Invalid measurement accepted: '+label)
        report.update(result='independent_locked_saved_wave_measurement_controls_verified', all_qualified=True,
            seventeen_gain_metrics=comparison, zero_and_undefined_reference_preserved=True,
            invalid_rejections=rejected, original_field_gate=2e-12, original_fidelity_gate=.02,
            no_producer_import_or_real_material_or_certified_FFT_bound=True)
    except BaseException as error:
        report.update(result='failed', error=repr(error))
        raise
    finally:
        save(args.out/'report.json', report)


if __name__ == '__main__':
    main()

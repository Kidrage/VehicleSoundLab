"""Known-first native frequency-region budgets without residual subtraction."""
import argparse
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args()
    repo = Path(__file__).resolve().parents[1]
    for name in ('OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'OMP_NUM_THREADS'):
        os.environ[name] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    from native_regions_v1.regions import labels, source_bounds
    from native_regions_v1.spectrum import measure
    from native_regions_v1.controls import cases, bounds
    a.out.mkdir(parents=True, exist_ok=False)
    r = dict(result='running', sources={}, inputs={}, known=[], cases=[])

    def source(path):
        r['inputs'][str(path)] = sha(path)
        return path

    def execute(name, audio, root_bounds, extra=None):
        folder = a.out/name
        folder.mkdir()
        region, coverage = labels(root_bounds, spec)
        outputs = [measure(audio[:, k:k+2], region, spec) for k in range(0, audio.shape[1], 2)]
        arrays = dict(audio=audio, root_bounds=root_bounds, regions=region,
                      interval_coverage_count=coverage,
                      window_starts=outputs[0]['window_starts'], region_bin_counts=outputs[0]['region_bin_counts'])
        for key in ['P_total', 'P_regions']:
            arrays[key] = np.stack([v[key] for v in outputs])
        error = abs(arrays['P_regions'].sum(axis=3)-arrays['P_total'])
        assert np.all(error <= gates['matrix_absolute_FS2']+gates['matrix_relative']*abs(arrays['P_total']))
        eigenvalues = np.linalg.eigvalsh(arrays['P_regions'])
        trace = arrays['P_regions'].diagonal(axis1=-2, axis2=-1).real.sum(axis=-1)
        assert np.all(eigenvalues[..., 0] >= -gates['matrix_absolute_FS2']-gates['matrix_relative']*trace)
        arrays['region_eigenvalues'] = eigenvalues
        if extra:
            arrays.update(extra)
        np.savez_compressed(folder/'arrays.npz', **arrays)
        return dict(label=name, stereo_inputs=audio.shape[1]//2, windows=len(root_bounds),
                    max_partition_matrix_error_FS2=float(error.max()),
                    minimum_literal_region_eigenvalue_FS2=float(eigenvalues.min()),
                    data_sha256=sha(folder/'arrays.npz')), arrays

    try:
        names = ['tools/run_F3_native_regions_v1.py', 'tools/research_archive_v1.py', 'research/F3_native_regions_v1_plan.json']
        names += [p.relative_to(repo).as_posix() for p in (repo/'tools/native_regions_v1').glob('*.py')]
        for name in names:
            dest = a.out/'exact_sources'/name
            dest.parent.mkdir(parents=True, exist_ok=True);shutil.copy2(repo/name, dest)
            r['sources'][name] = sha(dest)
        plan = load(repo/'research/F3_native_regions_v1_plan.json')
        spec, gates = plan['measurement'], plan['gates']
        for case in cases(plan):
            extra = {'known_envelope': case['envelope']} if 'envelope' in case else None
            row, arrays = execute('known_'+case['name'], case['audio'], bounds(case, spec), extra)
            trace = lambda p: p.diagonal(axis1=-2, axis2=-1).real.sum(axis=-1)
            total = float(trace(arrays['P_total']).sum())
            fractions = trace(arrays['P_regions']).sum(axis=(0, 1, 2))/total if total else np.zeros(4)
            row['region_power_fraction'] = fractions.tolist()
            if case['name'] in ['mono', 'asymmetric_phased']:
                assert fractions[1] <= gates['static_tone_interline_power_fraction_max'], fractions
            if case['name'] == 'static_interline':
                assert fractions[1] >= gates['static_half_order_interline_power_fraction_min'], fractions
            if case['name'] == 'rising_harmonics':
                assert fractions[1] <= gates['swept_harmonic_interline_power_fraction_max'], fractions
            if case['name'] == 'slow_AM':
                n = spec['window_samples'];window = .5-.5*np.cos(2*np.pi*np.arange(n)/n)
                amplitude2 = case['envelope']**2
                expected = np.array([np.dot(window**2, amplitude2[first:first+n])/np.dot(window, window)
                                     for first in arrays['window_starts']])[:, None]*np.array([.13**2, .09**2])[None, :]/2
                measured = arrays['P_total'][0, :, 6].diagonal(axis1=-2, axis2=-1).real
                error = float(abs(measured/expected-1).max())
                assert error <= gates['slow_AM_full_band_relative_error_max'], error
                row['known_AM_envelope_relative_error'] = error
            if case['name'].startswith('white_'):
                full_spec = dict(spec, bands_hz=[[0, 24000.001]])
                calibration = measure(case['audio'], arrays['regions'], full_spec)['P_total'].mean(axis=0)[0]
                rho = calibration[0, 1]/np.sqrt(calibration[0, 0].real*calibration[1, 1].real)
                assert abs(rho-.6) <= gates['known_white_full_band_correlation_absolute_error']
                row['known_full_band_correlation'] = [float(rho.real), float(rho.imag)]
            r['known'].append(row);save(a.out/'report.json', r)
            print('PASS known regions', case['name'], flush=True)
        r['known_passed_before_source'] = True
        parent = a.workspace/'baselines/F3_local_detail_budget_v1'
        manifest = load(source(parent/'manifest.json'))
        expected = {v['path']: v['sha256'] for v in manifest['files']}
        receipt = load(source(parent/'evidence/measure1/report.json'))
        assert sha(parent/'evidence/measure1/report.json') == expected['evidence/measure1/report.json']
        r['protected_before'] = receipt['protected_before']
        assert all(sha(repo/n) == h for n, h in r['protected_before'].items())
        for entry in receipt['cases']:
            path = source(parent/'evidence/measure1'/entry['label']/'measurement.npz')
            assert sha(path) == expected[path.relative_to(parent).as_posix()]
            original = np.load(path)
            audio, chunks = original['native'], original['C_chunks']
            coordinates_path = source(Path(entry['original_folder'])/'coordinates.npz')
            assert sha(coordinates_path) == receipt['inputs'][str(coordinates_path)]
            positions = np.load(coordinates_path)['source_seconds']
            first = entry['native_registered_start_seconds']+entry['native_first_frame']/48000
            starts = np.arange(0, len(audio)-spec['window_samples']+1, spec['hop_samples'])
            times = first+np.column_stack([starts, starts+spec['window_samples']-1])/48000
            root_bounds = source_bounds(positions, times)
            row, _ = execute(entry['label']+'_source', audio, root_bounds, dict(source_seconds=positions, window_times=times))
            c, _ = execute(entry['label']+'_C', chunks.transpose(1, 0, 2).reshape(len(audio), 18), root_bounds)
            r['cases'].append(dict(label=entry['label'], source=row, C=c,
                                   native_first_seconds=first, coordinate_input=str(coordinates_path)))
            save(a.out/'report.json', r);print('PASS shared native regions', entry['label'], flush=True)
        assert all(sha(repo/n) == h for n, h in r['protected_before'].items())
        r.update(result='native_frequency_regions_measured', known_cases=len(r['known']),
                 source_stereo_inputs=6, C_stereo_inputs=54, source_separation=False,
                 independent_noise_target=False, new_runtime_C_or_parameters=False,
                 physical_RPM_load_or_7_1_4=False)
    except Exception as exc:
        r.update(result='failed', error=repr(exc));raise
    finally:
        save(a.out/'report.json', r)


if __name__ == '__main__':
    main()

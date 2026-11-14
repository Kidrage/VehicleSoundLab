"""Measure six native-time stereo budgets without modifying fitted DNA or C."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
from research_archive_v1 import load, save, sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    for name in ('OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'OMP_NUM_THREADS'):
        os.environ[name] = '2'
    sys.path.insert(0, str(args.workspace/'tools/python_deps'))
    import numpy as np
    import soundfile as sf
    from local_detail_budget_v1.spectrum import known, matrices, describe, compare

    args.out.mkdir(parents=True, exist_ok=False)
    report = dict(result='running', sources={}, inputs={}, cases=[])

    def snapshot(name):
        dest = args.out/'exact_sources'/name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(repo/name, dest)
        report['sources'][name] = sha(dest)

    def source(path, manifest):
        relative = path.relative_to(manifest[0]).as_posix()
        actual = sha(path)
        assert manifest[1][relative] == actual, path
        report['inputs'][str(path)] = actual

    try:
        for name in ['tools/measure_F3_local_detail_budget_v1.py',
                     'tools/local_detail_budget_v1/spectrum.py',
                     'tools/research_archive_v1.py',
                     'research/F3_local_detail_budget_v1_plan.json']:
            snapshot(name)
        plan = load(repo/'research/F3_local_detail_budget_v1_plan.json')
        spec = plan['measurement']
        report['known_before_source'] = known(spec)
        save(args.out/'known.json', report['known_before_source'])
        print('PASS analytic mono/asymmetric/quadrature/delay and signed debt controls', flush=True)
        # Protect the authoritative runtime source/model inventory.
        parent = args.workspace/'baselines/catalog_local_F3_v1/evidence'
        protected = {}
        for name in ['C_files_sha256.json', 'voice_files_sha256.json']:
            values = load(parent/name)
            assert all(sha(repo/n) == h for n, h in values.items())
            protected.update(values)
        for name in ['experiments/modal_idle_v1/F2_fixed_idle.msource',
                     'experiments/modal_texture_v1/F2_amplitude.mtexture',
                     'experiments/spectral_texture_v1/F2_fine_static.sfir']:
            protected[name] = sha(repo/name)
        report['protected_before'] = protected
        index = load(repo/'voices/F3_fifth_local_v1/index.json')
        report['inputs']['voices/F3_fifth_local_v1/index.json'] = sha(repo/'voices/F3_fifth_local_v1/index.json')
        parents = {}
        for name in ['bandlimited_dna_v1', 'F3_pitch_anchors_v1', 'F3_fifth_voice_v1']:
            root = args.workspace/'baselines'/name
            manifest = load(root/'manifest.json')
            parents[name] = (root, {row['path']: row['sha256'] for row in manifest['files']})
            report['inputs'][str(root/'manifest.json')] = sha(root/'manifest.json')
        probe = args.workspace/plan['C']['probe']
        source(probe, parents['bandlimited_dna_v1'])
        (args.out/'bin').mkdir()
        shutil.copy2(probe, args.out/'bin'/probe.name)
        for case in plan['cases']:
            label = case['group']+'_'+case['point']
            folder = args.out/label
            folder.mkdir()
            original = parents[case['parent']][0]/'evidence/fit1'/case['case']
            for name in ['result.json', 'selection.json', 'coordinates.npz',
                         'native.wav', 'reference.wav', 'voice.model']:
                source(original/name, parents[case['parent']])
            profile_path = 'voices/F3_fifth_local_v1/'+label+'.model'
            row = next(p for p in index['profiles'] if p['path'] == profile_path)
            assert sha(repo/profile_path) == row['sha256'] == sha(original/'voice.model')
            report['inputs'][profile_path] = sha(repo/profile_path)
            result = load(original/'result.json')
            coordinates = np.load(original/'coordinates.npz')['source_seconds']
            native, rate = sf.read(original/'native.wav', always_2d=True)
            reference, reference_rate = sf.read(original/'reference.wav', always_2d=True)
            assert rate == reference_rate == 48000 and native.shape[1] == reference.shape[1] == 2
            registered = result['case']['seconds'][0]
            first = int(np.ceil((coordinates[0]-registered)*rate))
            last = int(np.floor((coordinates[-1]-registered)*rate))
            assert 0 <= first <= last < len(native)
            audio = native[first:last+1].copy()
            count = len(audio)
            assert count >= spec['window_samples']
            native_matrix = matrices(audio, spec)
            processed_matrix = matrices(reference, spec)
            waves = []
            chunks = []
            chunk_rows = []
            for seed in plan['C']['seeds']:
                dest = folder/('DNA_%d.wav' % seed)
                argv = list(map(str, [probe, repo/profile_path, dest, plan['C']['seconds'],
                                     row['root_hz'], plan['C']['detail'], seed, plan['C']['blocks']]))
                done = subprocess.run(argv, cwd=repo, capture_output=True, timeout=180)
                (folder/('C_%d.log' % seed)).write_bytes(done.stdout+done.stderr)
                assert done.returncode == 0, (label, seed, done.returncode)
                wave, rate = sf.read(dest, always_2d=True)
                assert wave.shape == (384000, 2) and rate == 48000 and np.isfinite(wave).all()
                waves.append(dict(seed=seed, argv=argv, sha256=sha(dest)))
                for seconds in plan['C']['chunk_start_seconds']:
                    start = round(seconds*rate)
                    assert start+count <= len(wave)
                    chunk = wave[start:start+count].copy()
                    chunks.append(chunk)
                    chunk_rows.append(dict(seed=seed, start_frame=start, frames=count))
            generated = np.array([matrices(chunk, spec) for chunk in chunks])
            average = generated.mean(axis=0)
            np.savez_compressed(folder/'measurement.npz', native=audio, processed=reference,
                                C_chunks=np.array(chunks), native_matrix=native_matrix,
                                processed_matrix=processed_matrix, C_matrices=generated,
                                C_mean=average, debt=native_matrix-generated,
                                mean_debt=native_matrix-average)
            entry = dict(case=case, label=label, root_hz=row['root_hz'],
                         original_folder=str(original), native_registered_start_seconds=registered,
                         frozen_source_range_seconds=[float(coordinates[0]), float(coordinates[-1])],
                         native_first_frame=first, native_last_frame_inclusive=last,
                         native_frames=count, processed_frames=len(reference),
                         native=describe(native_matrix), processed=describe(processed_matrix),
                         C_mean=describe(average), mean_comparison=compare(native_matrix, average),
                         comparisons=[compare(native_matrix, g) for g in generated],
                         generated=waves, chunks=chunk_rows,
                         data_sha256=sha(folder/'measurement.npz'))
            report['cases'].append(entry)
            save(args.out/'report.json', report)
            print('PASS native-time eight-band-matrix inputs', label, count, 'frames;9C chunks', flush=True)
        assert len(report['cases']) == 6
        assert all(sha(repo/name) == h for name, h in protected.items())
        report.update(result='six_native_time_stereo_budgets_measured',
                      runtime_C_voices_F2_exact=True, versions=dict(numpy=np.__version__, soundfile=sf.__version__),
                      audio_candidate_created=False, listening=False, physical_source_separation=False)
    except Exception as exc:
        report.update(result='failed', error=repr(exc))
        raise
    finally:
        save(args.out/'report.json', report)


if __name__ == '__main__':
    main()

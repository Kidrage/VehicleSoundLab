"""Supplement fixed analytic definitions, context identities and summaries."""
import argparse
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args(); sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    a.out.mkdir(parents=True, exist_ok=False); shutil.copy2(__file__, a.out/'executed_audit.py')
    root = a.workspace/'references/analysis/clock_c1_v1'
    r = dict(result='running', inputs={})
    def read(path):
        path = Path(path); r['inputs'][str(path)] = sha(path)
        if path.suffix == '.json':
            return load(path)
        with np.load(path) as z:
            return {k:z[k] for k in z.files}
    def summary(d, info, old):
        values = dict(nodes=len(d['x']), queries=len(d['query']),
            minimum_derivative_seconds_per_sample=float(d['interval_minimum_derivative'].min()),
            clock_change_max_seconds=float(np.max(abs(d['positions']-old))),
            old_second_difference_L2_seconds=float(np.linalg.norm(np.diff(old, 2))),
            C1_second_difference_L2_seconds=float(np.linalg.norm(np.diff(d['positions'], 2))))
        for key, value in values.items():
            assert info[key] == value
        assert info['node_preservation_max_seconds'] < 2e-12
    try:
        known = read(root/'known1/report.json'); real = read(root/'real1/report.json')
        for stage, proof in (('known1', 'known_audit1'), ('real1', 'audit1'), ('review1', 'review_audit1')):
            audit = read(root/proof/'report.json')
            assert audit['verification_passed'] and audit['producer_sha256'] == sha(root/stage/'report.json')
        tones = read(a.workspace/'references/analysis/locked_source_tail_v1/known1/capture.npz')
        for row in known['analytic']['cases']:
            d = read(root/'known1'/row['file']); assert sha(root/'known1'/row['file']) == row['sha256']
            for source, field in (('coefficients', 'tone_coefficients'), ('frequencies', 'frequencies'), ('taps', 'taps')):
                assert np.array_equal(d[field], tones[source])
            assert np.array_equal(d['x'], np.arange(-2048, 20481, 256, dtype=float))
            assert np.array_equal(d['query'], np.arange(18434, dtype=float))
            summary(d, row, d['exact'])
        old_root = a.workspace/'baselines/recorded_phase_context_v1/evidence/known1'
        previous = read(old_root/'report.json')
        for row in known['recorded']['cases']:
            original = next(c for c in previous['cases'] if c['label'] == row['label'])
            assert Path(row['source']).resolve() == (old_root/original['file']).resolve()
            assert sha(row['source']) == original['sha256']
            assert row['spec'] == original['spec'] and row['cutoff'] == original['info']['cutoff_hz']
            d = read(root/'known1'/row['file']); old = read(row['source'])
            summary(d, row, old['positions'])
        d = read(root/'real1/capture.npz'); summary(d, real['geometry'], d['old_positions'])
        cr = a.workspace/'baselines/recorded_phase_context_v1/evidence/real1'
        previous = read(cr/'report.json')
        original = next(c for c in previous['cases'] if c['label'] == real['label'])
        assert Path(real['context_file']).resolve() == (cr/original['file']).resolve()
        assert sha(real['context_file']) == original['sha256']
        centers = np.floor(d['source_query']).astype(np.int64)
        assert centers.min()+1-2048 >= 512
        assert centers.max()+2048 < len(d['filtered'])-512
        main = real['stereo']['bands'][:5]
        before = sum(real['observations']['signals']['original']['above18432']['Welch_FS2_LR'])
        after = sum(real['observations']['signals']['C1']['above18432']['Welch_FS2_LR'])
        metrics = dict(above_centre_original_LR_FS2=before, above_centre_C1_LR_FS2=after,
            above_centre_power_fraction=after/before,
            maximum_0_14k_power_change_dB=max(abs(v) for b in main for v in b['power_change_dB_LR']),
            maximum_0_14k_complex_coherence_difference=max(b['coherence_complex_difference'] for b in main),
            maximum_0_14k_Side_Mid_change_dB=max(abs(b['C1_Side_Mid_dB']-b['old_Side_Mid_dB']) for b in main),
            maximum_0_14k_CV_change=max(abs(v) for b in main for v in b['CV_change_LR']),
            maximum_0_14k_normalized_covariance_change=float(np.max(abs(d['C1__stereo_covariance'][:10, :10]-d['original__stereo_covariance'][:10, :10]))))
        r.update(result='independent_clock_c1_bindings_verified', verification_passed=True,
            analytic_controls=8, original_recorded_fixture_bindings=8,
            genuine_context_includes_all_FIR_and_long_kernel_support=True,
            all_geometry_summaries_verified=True, metrics=metrics,
            no_clock_truth_naturalness_or_source_admission_claim=True)
        save(a.out/'report.json', r); print('C1_BINDINGS_COMPLETE', metrics, flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error)); save(a.out/'report.json', r); raise


if __name__ == '__main__':
    main()

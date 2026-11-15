"""Independent complete summary/sensitivity/saved-fit cross-reference audit."""
import argparse
import os
from pathlib import Path
import shutil
import sys
from itertools import combinations
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for key in ('workspace', 'study', 'out'): p.add_argument('--'+key, type=Path, required=True)
    a = p.parse_args()
    for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'): os.environ[key] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    a.out.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, a.out/'executed_audit.py')
    s = load(a.study/'report.json'); assert s['result'] == 'source_resampling_review_published'
    for name, digest in s['inputs'].items(): assert sha(name) == digest
    for name, digest in s['sources'].items(): assert sha(a.study/'exact_sources'/name) == digest
    for name, digest in s['figures'].items(): assert sha(a.study/name) == digest
    real_path = next(Path(name) for name in s['inputs'] if Path(name).name == 'report.json' and Path(name).parent.name == 'real1' and 'source_resampling_v1' in Path(name).parts)
    real = load(real_path); checks = 0
    def check(x, y, absolute=False):
        nonlocal checks
        x, y = np.asarray(x), np.asarray(y)
        scale = 1. if absolute else float(np.max(abs(y)))
        error = float(np.max(abs(x-y)))
        assert error <= 2e-11*scale if scale else error == 0.
        checks += 1
    for row, c in zip(s['cases'], real['cases']):
        assert row['label'] == c['label']
        m = c['measurements']; changes = m['sinc128']['signed_stereo_and_temporal_changes_vs_legacy']
        for name in ('legacy', 'sinc64', 'sinc128', 'sinc256'): check(row['tail_Welch_FS2_LR'][name], m[name]['highest_split_Welch_FS2_LR'][-1])
        check(row['sinc128_over_legacy_tail_power'], sum(row['tail_Welch_FS2_LR']['sinc128'])/sum(row['tail_Welch_FS2_LR']['legacy']))
        check(row['main0_14k_max_abs_band_power_change_dB'], max(abs(v) for band in changes['power_change_dB'][:5] for v in band))
        check(row['main0_14k_max_abs_LR_complex_component_change'], max(abs(v) for band in changes['complex_coherence_change'][:5] for v in band))
        check(row['sinc128_target_wave_NRMSE_vs_legacy'], m['sinc128']['target_wave_NRMSE_vs_legacy'])
        with np.load(real_path.parent/c['file']) as z:
            for pair, (first, second) in zip(row['all_radius_pairs'], combinations(('sinc64', 'sinc128', 'sinc256'), 2)):
                assert (first, second) == (pair['first'], pair['second'])
                delta = z[first][2048:-2048]-z[second][2048:-2048]
                check(pair['target_wave_NRMSE_relative_legacy'], np.linalg.norm(delta)/np.linalg.norm(z['legacy'][2048:-2048]))
                check(pair['maximum_FS'], np.max(abs(delta)))
    capture = next(Path(name) for name in s['inputs'] if Path(name).name == 'capture.npz')
    with np.load(capture) as z: fitted, weights, amplitude = z['wave'][2048:-2048], z['weights'], float(z['amplitude'])
    targetfile = real_path.parent/'F3 Fifth First Early.npz'
    window = .5-.5*np.cos(2*np.pi*np.arange(4096)/4096)
    endpoint = np.r_[1., np.full(2047, 2.), 1.]
    bands = np.digitize(np.arange(2049)*16, [3000, 6000, 8000, 10000, 14000])
    with np.load(targetfile) as z:
        for name in ('legacy', 'sinc64', 'sinc128', 'sinc256'):
            target = z[name][2048:-2048]; cover = np.zeros(len(target))
            for start in range(-3840, len(target), 256):
                first, stop = max(0, start), min(len(target), start+4096)
                cover[first:stop] += window[first-start:stop-start]**2
            powers = np.zeros((2, 6))
            for start in range(0, len(target)-4096+1, 256):
                for j, audio in enumerate((target, fitted-target)):
                    X = np.fft.rfft(audio[start:start+4096]*window[:, None]/np.sqrt(cover[start:start+4096, None]), axis=0)
                    X *= (amplitude*np.sqrt(endpoint/4096)*weights)[:, None]
                    for band in range(6): powers[j, band] += np.sum(abs(X[bands == band])**2)
            check(s['saved_fit_cross_reference_complex_NRMSE'][name], np.sqrt(powers[1]/powers[0]))
    assert s['cross_reference_is_not_a_new_solver_or_fidelity_qualification']
    assert s['old_solution_cannot_be_reused_as_qualified_fit_to_new_reference']
    assert not s['original_source_fidelity_qualified'] and not s['eligible_for_later_source_statistics']
    assert len(s['cases']) == 6
    save(a.out/'report.json', dict(result='independent_source_resampling_review_verified',
        verification_passed=True, all_publication_fields_verified=True, numeric_checks=checks,
        all_18_radius_pairs_verified=True, saved_fit_regression_retained=True,
        original_fidelity_failure_retained=True, producer_sha256=sha(a.study/'report.json'), auditor_sha256=sha(__file__)))
    print('SOURCE_QUERY_REVIEW_AUDIT', checks, 'PASS', flush=True)


if __name__ == '__main__': main()

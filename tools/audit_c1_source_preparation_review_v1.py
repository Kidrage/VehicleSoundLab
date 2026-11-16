"""Independent physical bands/LR/MS/time/explicit FIR and every table number."""
import argparse
import csv
import math
import os
from pathlib import Path
import shutil
import sys
import xml.etree.ElementTree as ET
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for key in ('workspace', 'study', 'out'): p.add_argument('--'+key, type=Path, required=True)
    a = p.parse_args()
    for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'): os.environ[key] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    from clock_native_bridge_v1.audit_observation import verify
    a.out.mkdir(parents=True, exist_ok=False); shutil.copy2(__file__, a.out/'executed_audit.py')
    repo = Path(__file__).resolve().parents[1]
    r = dict(result='running', producer_sha256=sha(a.study/'report.json'), inputs={}, maximum_errors={}, signals=[])
    def check(name, actual, expected, scale, gate):
        actual, expected = np.asarray(actual), np.asarray(expected)
        assert actual.shape == expected.shape and np.isfinite(actual).all() and np.isfinite(expected).all(), name
        error = float(np.max(abs(actual-expected))) if actual.size else 0.
        error = error/scale if scale else error
        if not scale: assert error == 0
        assert error <= gate, (name, error, gate)
        r['maximum_errors'][name] = max(error, r['maximum_errors'].get(name, 0.))
    try:
        info = load(a.study/'report.json'); assert info['result'] == 'c1_source_preparation_bandwidth_published'
        for path, expected in info['inputs'].items(): assert sha(path) == expected; r['inputs'][path] = expected
        for name, expected in dict(info['figures'], **info['files']).items(): assert sha(a.study/name) == expected
        ET.parse(a.study/'source_bandwidth.svg')
        gates = load(repo/'research/native_clock_case_v1_plan.json')['gates']
        with np.load(a.study/'observations.npz') as f: z = {k:f[k] for k in f.files}
        ticks = z['native_indices']; assert np.array_equal(ticks, np.arange(info['first_native_tick'], info['stop_native_tick']))
        assert len(ticks) == info['physical_native_frames']
        ids = ticks-int(round(float(z['source_start'])*48000))
        assert np.array_equal(z['raw_audio'], z['native_source'][ids])
        for name in ('FIR14', 'FIR22'):
            assert np.array_equal(z[name+'_audio'], z[name+'_full'][ids-int(z[name+'_crop'][0])])
            taps = z[name+'_filter_taps']; assert np.array_equal(taps, taps[::-1]) and len(taps) == 1025
            offsets = np.arange(-512, 513)
            expected = abs(np.cos(2*np.pi*z['filter_frequency'][:, None]*offsets[None]/48000)@taps)
            check(name+'_independent_response', z[name+'_filter_magnitude'], expected, 1., 2e-12)
        for name in ('raw', 'FIR14', 'FIR22'):
            result = verify(name, z[name+'_audio'], z, check, gates)
            r['signals'].append(dict(name=name, verification=result))
        bands = {'broad':['0-3k', '3-6k', '6-8k', '8-10k', '10-14k', '14-24k'],
                 'upper':['14-16k', '16-20k', '20-22k', '22-24k']}
        with (a.study/'physical_bands.csv').open(encoding='utf-8', newline='') as f: rows = list(csv.DictReader(f))
        assert len(rows) == info['table_rows'] == 30
        frozen = {}
        for name in ('raw', 'FIR14', 'FIR22'):
            for scope in bands:
                power = z[name+'_'+scope+'_power']; mean = power.mean(axis=0)
                ms = z[name+'_'+scope+'_mid_side'].mean(axis=0)
                cross = z[name+'_broad_Gram'][:, :, 0, 1] if scope == 'broad' else z[name+'_upper_cross']
                coherence = cross.mean(axis=0)/np.sqrt(mean[:, 0]*mean[:, 1])
                frozen[name, scope] = mean, ms, coherence, power.std(axis=0)/mean
        values = 0
        for row in rows:
            name, scope, band = row['signal'], row['scope'], row['band']; i = bands[scope].index(band)
            mean, ms, coherence, cv = frozen[name, scope]
            expected = dict(L_FS2=mean[i, 0], R_FS2=mean[i, 1], Mid_FS2=ms[i, 0], Side_FS2=ms[i, 1],
                coherence_real=coherence[i].real, coherence_imag=coherence[i].imag, CV_L=cv[i, 0], CV_R=cv[i, 1])
            for key, value in expected.items():
                # Frozen-series arithmetic is verified independently above; exact publication roundtrip here.
                assert float(row[key]) == float(value), (name, scope, band, key, row[key], value)
                values += 1
        lookup = {(v['signal'], v['band']):v for v in rows}
        for name in ('raw', 'FIR14', 'FIR22'):
            highest = sum(float(lookup[name, '14-24k'][key]) for key in ('L_FS2', 'R_FS2'))
            lower = sum(float(lookup[name, band][key]) for band in bands['upper'][:3] for key in ('L_FS2', 'R_FS2'))
            check(name+'_published_upper_power', [info['metrics'][name]['LR_14_24k_FS2'], info['metrics'][name]['LR_14_22k_FS2']],
                [highest, lower], max(highest, lower), 2e-12)
        for name in ('FIR14', 'FIR22'):
            for band in ('14_24k', '14_22k'):
                m = info['metrics']; expected = 10*math.log10(m[name]['LR_'+band+'_FS2']/m['raw']['LR_'+band+'_FS2'])
                check(name+'_power_change_'+band, info['metrics'][name][band+'_power_change_from_raw_dB'], expected, 1., 2e-12)
        r.update(result='independent_c1_source_preparation_review_verified', verification_passed=True,
            published_numeric_values=values, independent_all2049bins_LR_MS_and_frozen_time_statistics=True,
            original_preparation_audit_still_failed=True, no_source_fidelity_or_runtime_or_hearing_promotion=True,
            no_certified_crossFFT_relative_weak_bin_bound=True)
        save(a.out/'report.json', r); print('C1_SOURCE_BANDWIDTH_INDEPENDENT', values, flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error)); save(a.out/'report.json', r); raise


if __name__ == '__main__': main()

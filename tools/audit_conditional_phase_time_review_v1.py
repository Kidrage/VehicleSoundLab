"""Recompute every published comparison and aggregate from audited raw arrays."""
import argparse
import math
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load, save, sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'study', 'review'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[name] = '2'
    sys.path.insert(0, str(args.workspace/'tools/python_deps'))
    import numpy as np
    shutil.copy2(__file__, args.review/'executed_metrics_verification.py')
    producer = load(args.study/'report.json')
    published = load(args.review/'figure_inputs.json')
    summary = load(args.review/'summary.json')
    lookup = {(row['label'], seed['seed']):(row, seed) for row in producer['cases'] for seed in row['seeds']}
    expected = []
    for row in published:
        case, seed = lookup[row['label'], row['seed']]
        name = row['variant']
        with np.load(args.study/row['label']/f'probe_{seed["seed"]}.npz') as raw:
            for field, prefix, target_prefix in [
                ('instantaneous', 'instant', 'line'), ('reobserved_line', 'line', 'line'), ('reobserved_broad', 'broad', 'broad')]:
                power = raw[name+'_'+prefix+'_mean']
                target = case['source_statistics'][target_prefix+'_mean']
                values = [10*math.log10(float(a)/float(b)) for a, b in zip(power, target)]
                assert abs(np.asarray(values)-row[field+'_power_error_dB']).max() < 2e-12
                coherence = raw[name+'_'+prefix+'_complex_coherence']
                target = case['source_statistics'][target_prefix+'_complex_coherence']
                values = [abs(complex(a)-complex(*b)) for a, b in zip(coherence, target)]
                assert abs(np.asarray(values)-row[field+'_coherence_error']).max() < 2e-12
                if prefix != 'instant':
                    values = [abs(float(a)-float(b)) for a, b in zip(raw[name+'_'+prefix+'_CV'],case['source_statistics'][prefix+'_CV'])]
                    assert abs(np.asarray(values)-row[field+'_CV_error']).max() < 2e-12
            values = [10*math.log10(float(a)/float(b)) for a, b in zip(raw[name+'_line_mean'], raw[name+'_instant_mean'])]
            assert abs(np.asarray(values)-row['line_to_instantaneous_power_dB']).max() < 2e-12
            assert np.array_equal(row['outside_P_fraction'], raw['outside_P_counts'].sum(axis=1)/65536)
            assert np.array_equal(row['maximum_phase_step_radians'], raw[name+'_maximum_unwrapped_relative_phase_step'] if name != 'fixed' else np.zeros(288))
            for prefix in ('line', 'broad'):
                target = case['source_statistics'][prefix+'_complex_coherence']
                values = [[abs(complex(a)-complex(*b)) for a, b in zip(chunk, target)]
                          for chunk in raw[name+'_chunks_'+prefix+'_complex_coherence']]
                assert abs(np.asarray(values)-row['matched_chunk_'+prefix+'_coherence_error']).max() < 2e-12
                values = [[abs(float(a)-float(b)) for a, b in zip(chunk, case['source_statistics'][prefix+'_CV'])]
                          for chunk in raw[name+'_chunks_'+prefix+'_CV']]
                assert abs(np.asarray(values)-row['matched_chunk_'+prefix+'_CV_error']).max() < 2e-12
                values = [[10*math.log10(float(a)/float(b)) for a, b in zip(chunk, case['source_statistics'][prefix+'_mean'])]
                          for chunk in raw[name+'_chunks_'+prefix+'_mean']]
                assert abs(np.asarray(values)-row['matched_chunk_'+prefix+'_power_error_dB']).max() < 2e-12
        expected.append((row['label'], row['seed'], name))
    assert len(expected) == len(set(expected)) == 90
    variants = ['fixed', 'relative', 'parent', 'density', 'variation']
    keys = [key for key in published[0] if key.endswith('_dB') or key.endswith('_error')]
    for variant in variants:
        chosen = [row for row in published if row['variant'] == variant]
        assert len(chosen) == 18
        for key in keys:
            values = [float(x) for row in chosen for x in np.asarray(row[key]).ravel()]
            actual = summary['variants'][variant][key]
            assert actual['count'] == len(values)
            assert abs(actual['mean']-math.fsum(values)/len(values)) < 2e-12
            assert abs(actual['mean_absolute']-math.fsum(abs(x) for x in values)/len(values)) < 2e-12
            assert abs(np.quantile(values, [0, .25, .5, .75, 1])-actual['quantiles']).max() < 2e-12
        phase = [float(x) for row in chosen for x in row['maximum_phase_step_radians']]
        assert np.array_equal(np.quantile(phase, [0, .25, .5, .75, 1]), summary['variants'][variant]['phase_step_per_harmonic_max_quantiles'])
    for pair, fields in summary['paired_absolute_error_counts'].items():
        variant, reference = pair.split('_vs_')
        a = {(r['label'], r['seed']):r for r in published if r['variant'] == variant}
        b = {(r['label'], r['seed']):r for r in published if r['variant'] == reference}
        assert a.keys() == b.keys()
        for key, counts in fields.items():
            actual = dict(improved=0, equal=0, regressed=0)
            for coordinate in a:
                for x, y in zip(np.asarray(a[coordinate][key]).ravel(), np.asarray(b[coordinate][key]).ravel()):
                    actual['improved' if abs(x) < abs(y) else 'regressed' if abs(x) > abs(y) else 'equal'] += 1
            assert actual == counts
    outside = [float(x) for row in published if row['variant'] == 'fixed' for x in row['outside_P_fraction']]
    assert np.array_equal(np.quantile(outside, [0, .25, .5, .75, 1]), summary['outside_P_fraction_quantiles'])
    save(args.review/'metrics_verification.json', dict(result='conditional_time_review_metrics_verified',
        all_90_rows_and_all_aggregates_verified=True, summary_sha256=sha(args.review/'summary.json'),
        figure_inputs_sha256=sha(args.review/'figure_inputs.json'), auditor_sha256=sha(__file__)))
    print('conditional_time_review_metrics_verified')


if __name__ == '__main__':
    main()

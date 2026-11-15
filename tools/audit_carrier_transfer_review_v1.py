"""Verify published signed budgets against full Gram arrays and original targets."""
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
    rows = load(args.review/'figure_inputs.json')
    pairs = load(args.review/'paired_inputs.json')
    summary = load(args.review/'summary.json')
    files = {(case['label'], seed['seed'], variant):case['label']+'/'+desc['file']
             for case in producer['cases'] for seed in case['seeds'] for variant, desc in seed['variants'].items()}
    assert len(rows) == len(files) == 90
    parent = args.workspace/'baselines/conditional_phase_time_v1/evidence/real1'
    for row in rows:
        with np.load(args.study/files[row['label'], row['seed'], row['variant']]) as raw, np.load(parent/row['label']/'source.npz') as original:
            for prefix in ('line', 'broad'):
                matrix = raw[prefix+'_Gram'].mean(axis=0)
                reference = original[prefix+'_mean'].reshape(4, 2)
                assert np.array_equal(row[prefix+'_reference_power'], reference)
                low = np.zeros((4, 2));rest = low.copy();cross = low.copy();total = low.copy();self_power = np.zeros((4, 6, 2))
                for band in range(4):
                    for channel in (0, 1):
                        for group in range(6):
                            self_power[band, group, channel] = matrix[band, 2*group+channel, 2*group+channel].real/reference[band, channel]
                        low[band, channel] = self_power[band, 0, channel]
                        rest[band, channel] = math.fsum(matrix[band, 2*g+channel, 2*h+channel].real for g in range(1, 6) for h in range(1, 6))/reference[band, channel]
                        cross[band, channel] = 2*math.fsum(matrix[band, channel, 2*h+channel].real for h in range(1, 6))/reference[band, channel]
                        total[band, channel] = math.fsum(matrix[band, 2*g+channel, 2*h+channel].real for g in range(6) for h in range(6))/reference[band, channel]
                for field, value in [('group_self', self_power), ('low_power', low), ('rest_power', rest),
                    ('signed_low_rest_cross', cross), ('total_power', total), ('signed_all_group_cross', total-self_power.sum(axis=1))]:
                    saved = np.asarray(row[prefix+'_'+field+'_over_reference'])
                    assert (abs(saved-value)/np.maximum(1.,abs(value))).max() < 2e-12
                assert (abs(low+rest+cross-total)/np.maximum(1.,abs(total))).max() < 2e-12
                assert abs(np.asarray(row[prefix+'_low_over_generated_total'])-low/total).max() < 2e-12
                assert abs(np.asarray(row[prefix+'_error_dB'])-10*np.log10(total)).max() < 2e-12
                for field, pairs_of_groups in [('low_LR',[(0,0)]), ('rest_LR',[(g,h) for g in range(1,6) for h in range(1,6)]),
                    ('cross_LR',[(0,h) for h in range(1,6)]+[(g,0) for g in range(1,6)])]:
                    values = [sum(matrix[b,2*g,2*h+1] for g,h in pairs_of_groups)/math.sqrt(reference[b,0]*reference[b,1]) for b in range(4)]
                    saved = np.asarray(row[prefix+'_'+field+'_over_reference'])
                    assert abs(saved[:,0]+1j*saved[:,1]-values).max() < 2e-12
    variants = ['fixed','relative','parent','density','variation']
    for name in variants:
        chosen = [row for row in rows if row['variant'] == name]
        assert len(chosen) == 18
        for prefix in ('line','broad'):
            self_power = np.asarray([row[prefix+'_group_self_over_reference'] for row in chosen])
            expected = np.array([[np.median(self_power[:,b,g,:]) for g in range(6)] for b in range(4)])
            assert np.array_equal(expected, summary['variants'][name][prefix+'_median_group_self_over_reference'])
            for field in ('low_power','rest_power','signed_low_rest_cross','signed_all_group_cross','total_power'):
                value = np.asarray([row[prefix+'_'+field+'_over_reference'] for row in chosen]).ravel()
                saved = summary['variants'][name][prefix+'_'+field]
                assert abs(math.fsum(value)/len(value)-saved['mean']) < 2e-12
                assert np.array_equal(np.quantile(value,[0,.25,.5,.75,1]),saved['quantiles'])
                assert int((value<0).sum())==saved['negative'] and int((value>0).sum())==saved['positive']
            ratios = np.asarray([row[prefix+'_low_over_generated_total'] for row in chosen])
            saved = summary['variants'][name][prefix+'_low_over_generated_total']
            assert np.array_equal(np.quantile(ratios,[0,.25,.5,.75,1]),saved['quantiles'])
            assert int((ratios>1).sum())==saved['above_one']
            assert np.array_equal([np.median(ratios[:,b,:]) for b in range(4)],saved['per_band_median'])
    by_key = {(row['label'],row['seed'],row['variant']):row for row in rows}
    assert len(pairs)==54
    for row in pairs:
        new=by_key[row['label'],row['seed'],row['variant']];old=by_key[row['label'],row['seed'],'relative']
        for key in row:
            if key not in ('label','seed','variant'):
                assert np.array_equal(row[key],np.asarray(new[key])-old[key])
        for prefix in ('line','broad'):
            residual=np.asarray(row[prefix+'_total_power_over_reference'])
            for field in ('low_power','rest_power','signed_low_rest_cross'):
                residual=residual-np.asarray(row[prefix+'_'+field+'_over_reference'])
            assert abs(residual).max()<2e-12
    for name in ('parent','density','variation'):
        chosen=[row for row in pairs if row['variant']==name]
        for key,saved in summary['paired_differences_vs_relative'][name].items():
            x=np.asarray([row[key] for row in chosen]).ravel()
            assert abs(math.fsum(x)/len(x)-saved['mean'])<2e-12
            assert np.array_equal(np.quantile(x,[0,.25,.5,.75,1]),saved['quantiles'])
            assert int((x>0).sum())==saved['positive'] and int((x<0).sum())==saved['negative']
    save(args.review/'metrics_verification.json',dict(result='carrier_transfer_review_metrics_verified',
        all90_rows_54_pairs_and_aggregates_verified=True,summary_sha256=sha(args.review/'summary.json'),
        figure_inputs_sha256=sha(args.review/'figure_inputs.json'),paired_inputs_sha256=sha(args.review/'paired_inputs.json'),auditor_sha256=sha(__file__)))
    print('carrier_transfer_review_metrics_verified')


if __name__=='__main__':
    main()

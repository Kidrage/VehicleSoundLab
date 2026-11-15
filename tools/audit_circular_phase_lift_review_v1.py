"""Independent full published-row/aggregate audit, with literal counts retained."""
import argparse
import math
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load,save,sha


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('workspace','study','review'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
        os.environ[name]='2'
    sys.path.insert(0,str(args.workspace/'tools/python_deps'))
    import numpy as np
    shutil.copy2(__file__,args.review/'executed_metrics_audit.py')
    producer=load(args.study/'report.json')
    rows=load(args.review/'figure_inputs.json')
    summary=load(args.review/'summary.json')
    descriptors={(case['label'],seed['seed'],name):desc for case in producer['cases'] for seed in case['seeds'] for name,desc in seed['variants'].items()}
    assert len(rows)==len(descriptors)==90
    assert len({(r['label'],r['seed'],r['variant']) for r in rows})==90
    parent=args.workspace/'baselines/conditional_phase_time_v1/evidence/real1'
    carrier=args.workspace/'baselines/carrier_transfer_v1/evidence/real1'
    for row in rows:
        label,seed,name=row['label'],row['seed'],row['variant']
        descriptor=descriptors[label,seed,name]
        with np.load(parent/label/'source.npz') as source,np.load(parent/label/f'probe_{seed}.npz') as raw,np.load(args.study/label/descriptor['file']) as new,np.load(carrier/label/f'{name}_{seed}.npz') as groups:
            assert sha(args.study/label/descriptor['file'])==descriptor['sha256']
            for prefix in ('line','broad'):
                reference=source[prefix+'_mean']
                for tag in ('raw','lift'):
                    values=raw if tag=='raw' else new
                    start=name+'_' if tag=='raw' else ''
                    expected=10*np.log10(values[start+prefix+'_mean']/reference)
                    assert abs(np.asarray(row[tag+'_'+prefix+'_power_error_dB'])-expected).max()<2e-12
                    for field,suffix in [('CV','CV_error'),('complex_coherence','coherence_error')]:
                        expected=abs(values[start+prefix+'_'+field]-source[prefix+'_'+field])
                        assert abs(np.asarray(row[tag+'_'+prefix+'_'+suffix])-expected).max()<2e-12
                    for field,suffix in [('mean','power_error_dB'),('CV','CV_error'),('complex_coherence','coherence_error')]:
                        value=values[start+'chunks_'+prefix+'_'+field]
                        expected=10*np.log10(value/reference) if field=='mean' else abs(value-source[prefix+'_'+field])
                        assert abs(np.asarray(row[tag+'_chunks_'+prefix+'_'+suffix])-expected).max()<2e-12
                for field in ('low_power','rest_power','signed_low_rest_cross','total_power'):
                    a=groups[prefix+'_'+field]/reference.reshape(4,2)
                    b=new[prefix+'_group_'+field]/reference.reshape(4,2)
                    for tag,value in [('raw',a),('lift',b),('delta',b-a)]:
                        assert abs(np.asarray(row[tag+'_'+prefix+'_'+field+'_over_reference'])-value).max()<2e-12
                residual=np.asarray(row['delta_'+prefix+'_total_power_over_reference'])
                for field in ('low_power','rest_power','signed_low_rest_cross'):
                    residual=residual-np.asarray(row['delta_'+prefix+'_'+field+'_over_reference'])
                assert abs(residual).max()<2e-12
            if name!='fixed':
                for field in ('branch_counts','changed_samples','ambiguous_steps','terminal_winding','maximum_raw_step','maximum_lifted_step','minimum_half_turn_margin'):
                    assert np.array_equal(row['lift_'+field],new['lift_'+field])
                assert row['branch_increments']==int(new['lift_branch_counts'].sum())
            else:
                assert row['branch_increments']==0
    tolerance={'power_error_dB':1e-8,'CV_error':2e-9,'coherence_error':2e-9}
    assert summary['comparison_tolerances']==tolerance
    def compare_counts(new,old,suffix,saved):
        d=new-old
        expected=dict(improved=int(np.count_nonzero(d < -tolerance[suffix])),
            equal_within_numeric_gate=int(np.count_nonzero(abs(d)<=tolerance[suffix])),
            regressed=int(np.count_nonzero(d > tolerance[suffix])),literal_improved=int(np.count_nonzero(new<old)),
            literal_equal=int(np.count_nonzero(new==old)),literal_regressed=int(np.count_nonzero(new>old)))
        assert expected==saved
    variants=('fixed','relative','parent','density','variation')
    by_key={(r['label'],r['seed']):r for r in rows if r['variant']=='relative'}
    for name in variants:
        chosen=[r for r in rows if r['variant']==name]
        assert len(chosen)==18
        for key,saved in summary['variants'][name].items():
            if key.startswith(('raw_','lift_','delta_')):
                values=np.concatenate([np.asarray(r[key]).ravel() for r in chosen])
                assert abs(math.fsum(values)/len(values)-saved['mean'])<2e-12
                assert abs(math.fsum(abs(values))/len(values)-saved['mean_absolute'])<2e-12
                assert np.array_equal(np.quantile(values,[0,.25,.5,.75,1]),saved['quantiles'])
                assert saved['count']==len(values)
        for prefix in ('line','broad','chunks_line','chunks_broad'):
            for suffix in tolerance:
                a=abs(np.concatenate([np.asarray(r['raw_'+prefix+'_'+suffix]).ravel() for r in chosen]))
                b=abs(np.concatenate([np.asarray(r['lift_'+prefix+'_'+suffix]).ravel() for r in chosen]))
                compare_counts(b,a,suffix,summary['variants'][name]['paired_'+prefix+'_'+suffix])
                if name in ('parent','density','variation'):
                    reference=abs(np.concatenate([np.asarray(by_key[r['label'],r['seed']]['raw_'+prefix+'_'+suffix]).ravel() for r in chosen]))
                    compare_counts(b,reference,suffix,summary['paired_vs_original_relative'][name][prefix+'_'+suffix])
        if name!='fixed':
            saved=summary['variants'][name]
            assert saved['branch_increments']==sum(r['branch_increments'] for r in chosen)
            assert saved['partials_with_crossings']==sum(np.count_nonzero(r['lift_branch_counts']) for r in chosen)
            assert saved['ambiguous_steps']==sum(np.sum(r['lift_ambiguous_steps']) for r in chosen)
            for field in ('maximum_raw_step','maximum_lifted_step','minimum_half_turn_margin'):
                assert np.array_equal(np.quantile([r['lift_'+field] for r in chosen],[0,.25,.5,.75,1]),saved[field+'_quantiles'])
    result=dict(result='circular_phase_lift_published_metrics_verified',all90_rows_and_aggregates_verified=True,
        literal_and_numerical_equivalence_counts_verified=True,figure_inputs_sha256=sha(args.review/'figure_inputs.json'),
        summary_sha256=sha(args.review/'summary.json'),auditor_sha256=sha(__file__))
    save(args.review/'metrics_verification.json',result)
    print(result['result'])


if __name__=='__main__':
    main()

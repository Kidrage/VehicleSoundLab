"""All raw/lifted/source comparisons, retaining regressions and signed budgets."""
import numpy as np


def collect(producer, study, parent, carrier):
    rows = []
    for case in producer['cases']:
        label = case['label']
        with np.load(parent/label/'source.npz') as raw:
            source = {name:raw[name] for prefix in ('line','broad') for name in (prefix+'_mean',prefix+'_CV',prefix+'_complex_coherence')}
        for seed in case['seeds']:
            with np.load(parent/label/f'probe_{seed["seed"]}.npz') as raw:
                previous = {name+'_'+field:raw[name+'_'+field] for name in seed['variants'] for field in (
                    'line_mean','broad_mean','line_CV','broad_CV','line_complex_coherence','broad_complex_coherence',
                    'chunks_line_mean','chunks_broad_mean','chunks_line_CV','chunks_broad_CV',
                    'chunks_line_complex_coherence','chunks_broad_complex_coherence')}
            for name, desc in seed['variants'].items():
                row = dict(label=label,seed=seed['seed'],variant=name,branch_increments=desc['branch_increments'])
                with np.load(study/label/desc['file']) as new, np.load(carrier/label/f'{name}_{seed["seed"]}.npz') as old:
                    for prefix in ('line','broad'):
                        reference = source[prefix+'_mean'].reshape(4,2)
                        for tag,mean,cv,coherence in [('raw',previous[name+'_'+prefix+'_mean'],previous[name+'_'+prefix+'_CV'],previous[name+'_'+prefix+'_complex_coherence']),
                            ('lift',new[prefix+'_mean'],new[prefix+'_CV'],new[prefix+'_complex_coherence'])]:
                            row[tag+'_'+prefix+'_power_error_dB'] = (10*np.log10(mean/source[prefix+'_mean'])).tolist()
                            row[tag+'_'+prefix+'_CV_error'] = abs(cv-source[prefix+'_CV']).tolist()
                            row[tag+'_'+prefix+'_coherence_error'] = abs(coherence-source[prefix+'_complex_coherence']).tolist()
                            for field in ('mean','CV','complex_coherence'):
                                value = previous[name+'_chunks_'+prefix+'_'+field] if tag == 'raw' else new['chunks_'+prefix+'_'+field]
                                if field == 'mean':
                                    result = 10*np.log10(value/source[prefix+'_mean'])
                                    key = 'power_error_dB'
                                else:
                                    result = abs(value-source[prefix+'_'+field])
                                    key = 'CV_error' if field == 'CV' else 'coherence_error'
                                row[tag+'_chunks_'+prefix+'_'+key] = result.tolist()
                        for field in ('low_power','rest_power','signed_low_rest_cross','total_power'):
                            raw = old[prefix+'_'+field]/reference
                            lifted = new[prefix+'_group_'+field]/reference
                            row['raw_'+prefix+'_'+field+'_over_reference'] = raw.tolist()
                            row['lift_'+prefix+'_'+field+'_over_reference'] = lifted.tolist()
                            row['delta_'+prefix+'_'+field+'_over_reference'] = (lifted-raw).tolist()
                    if name!='fixed':
                        for field in ('branch_counts','changed_samples','ambiguous_steps','terminal_winding','maximum_raw_step','maximum_lifted_step','minimum_half_turn_margin'):
                            row['lift_'+field] = new['lift_'+field].tolist()
                rows.append(row)
    return rows


def summarize(rows):
    variants = {}
    # Propagate the already frozen 2e-9 dimensionless statistics gate into dB
    # (10/log(10) times a small relative power error). Keep literal counts too.
    tolerance = dict(power_error_dB=1e-8,CV_error=2e-9,coherence_error=2e-9)
    def counts(new, old, suffix):
        difference = new-old
        return dict(improved=int((difference < -tolerance[suffix]).sum()),
            equal_within_numeric_gate=int((abs(difference) <= tolerance[suffix]).sum()),
            regressed=int((difference > tolerance[suffix]).sum()),
            literal_improved=int((new<old).sum()),literal_equal=int((new==old).sum()),literal_regressed=int((new>old).sum()))
    keys = [key for key in rows[0] if key.startswith(('raw_','lift_','delta_')) and key.endswith(('error_dB','_error','_over_reference'))]
    for name in ('fixed','relative','parent','density','variation'):
        chosen = [r for r in rows if r['variant']==name]
        values = {}
        for key in keys:
            x = np.concatenate([np.asarray(r[key]).ravel() for r in chosen])
            values[key] = dict(mean=float(x.mean()),mean_absolute=float(abs(x).mean()),
                quantiles=np.quantile(x,[0,.25,.5,.75,1]).tolist(),count=int(x.size))
        for prefix in ('line','broad','chunks_line','chunks_broad'):
            for suffix in ('power_error_dB','CV_error','coherence_error'):
                raw = abs(np.concatenate([np.asarray(r['raw_'+prefix+'_'+suffix]).ravel() for r in chosen]))
                lifted = abs(np.concatenate([np.asarray(r['lift_'+prefix+'_'+suffix]).ravel() for r in chosen]))
                values['paired_'+prefix+'_'+suffix] = counts(lifted,raw,suffix)
        if name!='fixed':
            values['branch_increments'] = sum(r['branch_increments'] for r in chosen)
            values['partials_with_crossings'] = int(sum(np.count_nonzero(r['lift_branch_counts']) for r in chosen))
            values['ambiguous_steps'] = int(sum(np.sum(r['lift_ambiguous_steps']) for r in chosen))
            for field in ('maximum_raw_step','maximum_lifted_step','minimum_half_turn_margin'):
                values[field+'_quantiles'] = np.quantile(np.asarray([r['lift_'+field] for r in chosen]),[0,.25,.5,.75,1]).tolist()
        variants[name] = values
    reference = {(r['label'],r['seed']):r for r in rows if r['variant']=='relative'}
    paired = {}
    for name in ('parent','density','variation'):
        chosen = [r for r in rows if r['variant']==name]
        result = {}
        for prefix in ('line','broad','chunks_line','chunks_broad'):
            for suffix in ('power_error_dB','CV_error','coherence_error'):
                new = abs(np.concatenate([np.asarray(r['lift_'+prefix+'_'+suffix]).ravel() for r in chosen]))
                old = abs(np.concatenate([np.asarray(reference[r['label'],r['seed']]['raw_'+prefix+'_'+suffix]).ravel() for r in chosen]))
                result[prefix+'_'+suffix] = counts(new,old,suffix)
        paired[name] = result
    return dict(variants=variants,paired_vs_original_relative=paired,comparison_tolerances=tolerance,all90_rows_retained=True,
        normalized_coordinate_only=True,numeric_not_listening_acceptance=True,
        seeds_not_independent_recordings=True,source_count_chunks_have_overlapping_apertures=True)

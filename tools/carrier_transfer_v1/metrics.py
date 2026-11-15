"""Signed carrier-origin budgets normalized to original source band powers."""
import numpy as np


def collect(producer, study, parent):
    rows = []
    for case in producer['cases']:
        with np.load(parent/case['label']/'source.npz') as source:
            targets = {prefix:source[prefix+'_mean'].reshape(4, 2) for prefix in ('line', 'broad')}
        for seed in case['seeds']:
            for name, descriptor in seed['variants'].items():
                row = dict(label=case['label'], seed=seed['seed'], variant=name)
                with np.load(study/case['label']/descriptor['file']) as raw:
                    for prefix in ('line', 'broad'):
                        target = targets[prefix]
                        row[prefix+'_reference_power'] = target.tolist()
                        row[prefix+'_group_self_over_reference'] = (raw[prefix+'_group_self_power']/target[:, None, :]).tolist()
                        for field in ('low_power', 'rest_power', 'signed_low_rest_cross', 'signed_all_group_cross', 'total_power'):
                            row[prefix+'_'+field+'_over_reference'] = (raw[prefix+'_'+field]/target).tolist()
                        low = raw[prefix+'_low_power']
                        total = raw[prefix+'_total_power']
                        row[prefix+'_low_over_generated_total'] = (low/total).tolist()
                        row[prefix+'_error_dB'] = (10*np.log10(total/target)).tolist()
                        # Cross-channel low/rest terms must stay complex; the
                        # LR interference term is not twice a real scalar.
                        matrix = raw[prefix+'_Gram'].mean(axis=0)
                        low_LR = matrix[:, 0, 1]
                        rest_LR = matrix[:, 2::2, 3::2].sum(axis=(1, 2))
                        cross_LR = matrix[:, 0, 3::2].sum(axis=1)+matrix[:, 2::2, 1].sum(axis=1)
                        for field, value in [('low_LR', low_LR), ('rest_LR', rest_LR), ('cross_LR', cross_LR)]:
                            normalized = value/np.sqrt(target[:, 0]*target[:, 1])
                            row[prefix+'_'+field+'_over_reference'] = np.stack([normalized.real, normalized.imag], axis=-1).tolist()
                rows.append(row)
    return rows


def summarize(rows):
    variants = {}
    for name in ('fixed', 'relative', 'parent', 'density', 'variation'):
        selected = [row for row in rows if row['variant'] == name]
        values = {}
        for prefix in ('line', 'broad'):
            group = np.array([row[prefix+'_group_self_over_reference'] for row in selected])
            values[prefix+'_median_group_self_over_reference'] = np.median(group, axis=(0, 3)).tolist()
            for field in ('low_power', 'rest_power', 'signed_low_rest_cross', 'signed_all_group_cross', 'total_power'):
                value = np.array([row[prefix+'_'+field+'_over_reference'] for row in selected])
                values[prefix+'_'+field] = dict(mean=float(value.mean()), quantiles=np.quantile(value, [0, .25, .5, .75, 1]).tolist(),
                                               negative=int((value < 0).sum()), positive=int((value > 0).sum()))
            ratio = np.array([row[prefix+'_low_over_generated_total'] for row in selected])
            values[prefix+'_low_over_generated_total'] = dict(quantiles=np.quantile(ratio, [0, .25, .5, .75, 1]).tolist(),
                                                             per_band_median=np.median(ratio, axis=(0, 2)).tolist(),
                                                             above_one=int((ratio > 1).sum()))
        variants[name] = values
    pairs = []
    baseline = {(row['label'], row['seed']):row for row in rows if row['variant'] == 'relative'}
    for row in rows:
        if row['variant'] not in ('parent', 'density', 'variation'):
            continue
        original = baseline[row['label'], row['seed']]
        record = {key:row[key] for key in ('label', 'seed', 'variant')}
        for prefix in ('line', 'broad'):
            for field in ('low_power', 'rest_power', 'signed_low_rest_cross', 'total_power'):
                key = prefix+'_'+field+'_over_reference'
                record[key] = (np.asarray(row[key])-original[key]).tolist()
        pairs.append(record)
    paired_summary = {}
    for name in ('parent', 'density', 'variation'):
        selected = [row for row in pairs if row['variant'] == name]
        values = {}
        for prefix in ('line', 'broad'):
            for field in ('low_power', 'rest_power', 'signed_low_rest_cross', 'total_power'):
                key = prefix+'_'+field+'_over_reference'
                x = np.asarray([row[key] for row in selected])
                values[key] = dict(mean=float(x.mean()), quantiles=np.quantile(x, [0, .25, .5, .75, 1]).tolist(),
                                  positive=int((x > 0).sum()), negative=int((x < 0).sum()))
        paired_summary[name] = values
    return dict(variants=variants, paired_differences_vs_relative=paired_summary,
                normalization='Each own original source/context band/channel power; ratios are not physical energy shares',
                signed_cross_preserved=True, all90_alternatives_retained=True), pairs

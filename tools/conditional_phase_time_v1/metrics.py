"""Keep instantaneous, projected-line and broadband comparisons separate."""
import numpy as np


def comparisons(producer, study):
    rows = []
    for case in producer['cases']:
        source = case['source_statistics']
        source_line_coherence = np.asarray(source['line_complex_coherence'])
        source_line_coherence = source_line_coherence[:, 0]+1j*source_line_coherence[:, 1]
        source_broad_coherence = np.asarray(source['broad_complex_coherence'])
        source_broad_coherence = source_broad_coherence[:, 0]+1j*source_broad_coherence[:, 1]
        for seed in case['seeds']:
            with np.load(study/case['label']/f'probe_{seed["seed"]}.npz') as capture:
                for variant in seed['variants']:
                    def get(name):
                        return capture[variant+'_'+name]
                    def decibels(a, b):
                        return 10*np.log10(np.maximum(a, 1e-30)/np.maximum(b, 1e-30))
                    rows.append(dict(
                        label=case['label'], seed=seed['seed'], variant=variant,
                        instantaneous_power_error_dB=decibels(get('instant_mean'), source['line_mean']).tolist(),
                        reobserved_line_power_error_dB=decibels(get('line_mean'), source['line_mean']).tolist(),
                        reobserved_broad_power_error_dB=decibels(get('broad_mean'), source['broad_mean']).tolist(),
                        line_to_instantaneous_power_dB=decibels(get('line_mean'), get('instant_mean')).tolist(),
                        instantaneous_coherence_error=abs(get('instant_complex_coherence')-source_line_coherence).tolist(),
                        reobserved_line_coherence_error=abs(get('line_complex_coherence')-source_line_coherence).tolist(),
                        reobserved_broad_coherence_error=abs(get('broad_complex_coherence')-source_broad_coherence).tolist(),
                        reobserved_line_CV_error=abs(get('line_CV')-source['line_CV']).tolist(),
                        reobserved_broad_CV_error=abs(get('broad_CV')-source['broad_CV']).tolist(),
                        outside_P_fraction=np.asarray(seed['outside_P_fraction']).tolist(),
                        maximum_phase_step_radians=(capture[variant+'_maximum_unwrapped_relative_phase_step'].tolist()
                            if variant != 'fixed' else [0.]*288)))
                    for prefix in ('line', 'broad'):
                        target = np.asarray(source[prefix+'_complex_coherence'])
                        target = target[:, 0]+1j*target[:, 1]
                        rows[-1]['matched_chunk_'+prefix+'_coherence_error'] = abs(
                            get('chunks_'+prefix+'_complex_coherence')-target).tolist()
                        rows[-1]['matched_chunk_'+prefix+'_CV_error'] = abs(
                            get('chunks_'+prefix+'_CV')-source[prefix+'_CV']).tolist()
                        rows[-1]['matched_chunk_'+prefix+'_power_error_dB'] = decibels(
                            get('chunks_'+prefix+'_mean'), source[prefix+'_mean']).tolist()
    return rows


def summarize(rows):
    keys = [key for key in rows[0] if key.endswith('_dB') or key.endswith('_error')]
    result = {}
    variants = ('fixed', 'relative', 'parent', 'density', 'variation')
    for variant in variants:
        selected = [row for row in rows if row['variant'] == variant]
        values = {}
        for key in keys:
            all_values = np.concatenate([np.asarray(row[key]).ravel() for row in selected])
            values[key] = dict(mean=float(all_values.mean()), mean_absolute=float(abs(all_values).mean()),
                               quantiles=np.quantile(all_values, [0, .25, .5, .75, 1]).tolist(), count=int(all_values.size))
        phase = np.asarray([row['maximum_phase_step_radians'] for row in selected])
        values['phase_step_per_harmonic_max_quantiles'] = np.quantile(phase, [0, .25, .5, .75, 1]).tolist()
        result[variant] = values
    pairs = {}
    for variant in variants[1:]:
        for reference in ('fixed', 'relative'):
            if reference == variant:
                continue
            a = [row for row in rows if row['variant'] == variant]
            b = [row for row in rows if row['variant'] == reference]
            assert [(r['label'], r['seed']) for r in a] == [(r['label'], r['seed']) for r in b]
            values = {}
            for key in keys:
                x = abs(np.concatenate([np.asarray(r[key]).ravel() for r in a]))
                y = abs(np.concatenate([np.asarray(r[key]).ravel() for r in b]))
                values[key] = dict(improved=int((x < y).sum()), equal=int((x == y).sum()), regressed=int((x > y).sum()))
            pairs[variant+'_vs_'+reference] = values
    return dict(variants=result, paired_absolute_error_counts=pairs,
                outside_P_fraction_quantiles=np.quantile(np.asarray([row['outside_P_fraction'] for row in rows if row['variant'] == 'fixed']), [0, .25, .5, .75, 1]).tolist(),
                counts_are_numeric_not_perceptual=True, repeated_source_seeds_not_independent_recordings=True)

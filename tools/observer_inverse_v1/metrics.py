"""Descriptive errors for all inverse attempts, never sound-quality scores."""
import numpy as np
from research_archive_v1 import load, sha

VARIANTS = ('interpolated', 'original4000', 'preconditioned4000', 'corrected')


def collect(root):
    reports = {name:load(root/name/'report.json') for name in ('real1','real2','real3')}
    assert all(r['result'] == 'observer_inverse_all6_measured' and len(r['cases']) == 6 for r in reports.values())
    rows, solves, inputs = [], [], {}
    for name in reports:
        inputs[str(root/name/'report.json')] = sha(root/name/'report.json')
    for j in range(6):
        original = reports['real1']['cases'][j]
        label = original['label']
        path = root/'real1'/label/'source.npz'
        assert sha(path) == original['source_sha256']
        inputs[str(path)] = sha(path)
        with np.load(path) as z:
            source = {k:z[k] for k in ('audio','coefficients','line_mean','line_CV',
                'line_complex_coherence','broad_mean','broad_CV','broad_complex_coherence')}
        paths = [('interpolated', 'real1', 'interpolated_observations'),
            ('original4000','real1','inverse'), ('preconditioned4000','real2','inverse'),
            ('corrected','real3','inverse')]
        for variant, attempt, key in paths:
            case = reports[attempt]['cases'][j]
            assert case['label'] == label and case['root_hz'] == original['root_hz']
            desc = case['variants'][key];path = root/attempt/label/desc['file']
            assert sha(path) == desc['sha256'];inputs[str(path)] = sha(path)
            with np.load(path) as z:
                row = dict(label=label, variant=variant, root_hz=case['root_hz'],
                    wave_NRMSE=float(z['wave_NRMSE']),
                    wave_region_NRMSE=z['wave_region_NRMSE'].tolist())
                for prefix in ('line','broad'):
                    row[prefix+'_power_error_dB'] = (10*np.log10(np.maximum(z[prefix+'_mean'],1e-24)/np.maximum(source[prefix+'_mean'],1e-24))).reshape(-1,2).tolist()
                    row[prefix+'_coherence_error'] = abs(z[prefix+'_complex_coherence']-source[prefix+'_complex_coherence']).tolist()
                    row[prefix+'_CV_error'] = abs(z[prefix+'_CV']-source[prefix+'_CV']).reshape(-1,2).tolist()
                rows.append(row)
        for attempt in reports:
            case = reports[attempt]['cases'][j]
            solves.append(dict(label=label, attempt=attempt, **case['solve'],
                cumulative_iterations=case.get('cumulative_iterations',case['solve']['iterations']),
                correction_stages=case.get('correction_stages',[])))
    return rows, solves, inputs


def summarize(rows, solves):
    result = dict(variants={}, paired={}, source_models=6, engines=1,
        source_context='F3 two ascents, early/mid/late; in-sample normalized-coordinate diagnostic',
        solver_converged={name:sum(s['converged'] for s in solves if s['attempt']==name) for name in ('real1','real2','real3')})
    for name in VARIANTS:
        rr = [r for r in rows if r['variant']==name]
        result['variants'][name] = dict(
            wave_NRMSE_mean=float(np.mean([r['wave_NRMSE'] for r in rr])),
            wave_region_NRMSE_mean=np.mean([r['wave_region_NRMSE'] for r in rr],axis=0).tolist(),
            **{key+'_mean':float(np.mean([abs(np.asarray(r[key])) for r in rr]))
               for key in ('line_power_error_dB','broad_power_error_dB',
                           'line_coherence_error','broad_coherence_error','line_CV_error','broad_CV_error')})
        if name == 'interpolated':
            continue
        base = {r['label']:r for r in rows if r['variant']=='interpolated'}
        comparisons = {}
        for key in ('wave_NRMSE','wave_region_NRMSE','broad_power_error_dB','broad_coherence_error','broad_CV_error'):
            delta = np.array([abs(np.asarray(r[key]))-abs(np.asarray(base[r['label']][key])) for r in rr])
            comparisons[key] = dict(mean_change=float(delta.mean()), improved=int((delta < -1e-12).sum()),
                regressed=int((delta > 1e-12).sum()), equivalent=int((abs(delta)<=1e-12).sum()), count=delta.size)
        result['paired'][name+'_minus_interpolated'] = comparisons
    return result

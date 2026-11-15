"""All shared-metric fits and frozen baselines, including original weak-band errors."""
import numpy as np
from research_archive_v1 import load, sha
from conditional_phase_time_v1.observer import power_statistics
from observer_complete_v1.metrics import ERRORS

VARIANTS = ('interpolated', 'old_original4000', 'old_corrected', 'complete', 'weighted')


def collect(study):
    report = load(study/'report.json')
    assert report['result'] == 'observer_frequency_all6_measured'
    rows, solves = [], []
    inputs = {str(study/'report.json'): sha(study/'report.json')}
    for case in report['cases']:
        folder = study/case['label']; path = folder/'source.npz'
        assert sha(path) == case['source_sha256']; inputs[str(path)] = sha(path)
        with np.load(path) as z: source = {k: z[k] for k in z.files}
        parts = [power_statistics(source['broadband_power'][indices], source['broadband_cross'][indices])
            for indices in np.array_split(np.arange(case['source_rows']), 3)]
        for field in ('mean', 'CV', 'complex_coherence'):
            source['chunks_broad_'+field] = np.stack([p[field] for p in parts])
        for tag in VARIANTS:
            desc = case['variants'][tag]; path = folder/desc['file']
            assert sha(path) == desc['sha256']; inputs[str(path)] = sha(path)
            with np.load(path) as z:
                row = dict(label=case['label'], variant=tag, root_hz=case['root_hz'],
                    weighted_objective=desc['weighted_objective'], wave_NRMSE=float(z['wave_NRMSE']),
                    wave_region_NRMSE=z['wave_region_NRMSE'].tolist(),
                    source_broad_mean=source['broad_mean'].reshape(-1, 2).tolist(),
                    rendered_broad_mean=z['broad_mean'].reshape(-1, 2).tolist())
                for prefix in ('line', 'broad', 'chunks_broad'):
                    shape = (3, -1, 2) if prefix == 'chunks_broad' else (-1, 2)
                    row[prefix+'_power_error_dB'] = (10*np.log10(np.maximum(z[prefix+'_mean'], 1e-24)/
                        np.maximum(source[prefix+'_mean'], 1e-24))).reshape(shape).tolist()
                    row[prefix+'_coherence_error'] = abs(z[prefix+'_complex_coherence']-
                        source[prefix+'_complex_coherence']).tolist()
                    row[prefix+'_CV_error'] = abs(z[prefix+'_CV']-source[prefix+'_CV']).reshape(shape).tolist()
                rows.append(row)
        solves.append(dict(label=case['label'], **case['solve']))
    assert len(rows) == 30 and len(solves) == 6
    return rows, solves, inputs


def summarize(rows, solves):
    result = dict(source_models=6, engines=1, ascents=2, in_sample_only=True,
        solver_converged=sum(r['converged'] for r in solves),
        solver_stop_codes=[r['stop'] for r in solves], variants={}, paired={})
    for tag in VARIANTS:
        rr = [r for r in rows if r['variant'] == tag]
        result['variants'][tag] = dict(
            weighted_objective_mean=float(np.mean([r['weighted_objective'] for r in rr])),
            **{k+'_mean': float(np.mean(abs(np.array([r[k] for r in rr])))) for k in ERRORS},
            wave_region_NRMSE_by_region=np.mean([r['wave_region_NRMSE'] for r in rr], axis=0).tolist(),
            broad_signed_power_error_dB_by_band=np.mean([r['broad_power_error_dB'] for r in rr], axis=(0, 2)).tolist())
    candidate = {r['label']: r for r in rows if r['variant'] == 'weighted'}
    for tag in VARIANTS[:-1]:
        comparison = {}
        for key in ERRORS:
            delta = np.array([abs(np.asarray(candidate[r['label']][key]))-abs(np.asarray(r[key]))
                for r in rows if r['variant'] == tag])
            comparison[key] = dict(mean_change=float(delta.mean()), improved=int((delta < -1e-12).sum()),
                regressed=int((delta > 1e-12).sum()), equivalent=int((abs(delta) <= 1e-12).sum()), count=int(delta.size))
        result['paired']['weighted_minus_'+tag] = comparison
    return result

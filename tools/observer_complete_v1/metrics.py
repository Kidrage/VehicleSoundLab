"""Complete-data and original-observer diagnostics, without listening scores."""
import numpy as np
from research_archive_v1 import load, sha
from conditional_phase_time_v1.observer import power_statistics

VARIANTS = ('interpolated', 'old_original4000', 'old_corrected', 'complete')
ERRORS = ('wave_NRMSE', 'wave_region_NRMSE', 'line_power_error_dB',
          'broad_power_error_dB', 'line_coherence_error', 'broad_coherence_error',
          'line_CV_error', 'broad_CV_error', 'chunks_broad_power_error_dB',
          'chunks_broad_coherence_error', 'chunks_broad_CV_error')


def collect(study):
    record = load(study/'report.json')
    assert record['result'] == 'observer_complete_all6_measured'
    rows, solves = [], []
    inputs = {str(study/'report.json'): sha(study/'report.json')}
    for case in record['cases']:
        folder = study/case['label']
        path = folder/'source.npz'
        assert sha(path) == case['source_sha256']
        inputs[str(path)] = sha(path)
        with np.load(path) as cap:
            source = {k: cap[k] for k in cap.files}
        chunks = [power_statistics(source['broadband_power'][part],
            source['broadband_cross'][part]) for part in
            np.array_split(np.arange(case['source_rows']), 3)]
        for field in ('mean', 'CV', 'complex_coherence'):
            source['chunks_broad_'+field] = np.stack([part[field] for part in chunks])
        for name in VARIANTS:
            desc = case['variants'][name]
            path = folder/desc['file']
            assert sha(path) == desc['sha256']
            inputs[str(path)] = sha(path)
            with np.load(path) as z:
                row = dict(label=case['label'], variant=name,
                    root_hz=case['root_hz'], source_rows=case['source_rows'],
                    wave_NRMSE=float(z['wave_NRMSE']),
                    wave_region_NRMSE=z['wave_region_NRMSE'].tolist(),
                    new_objective=desc['new_objective'],
                    source_broad_mean=source['broad_mean'].reshape(-1, 2).tolist(),
                    rendered_broad_mean=z['broad_mean'].reshape(-1, 2).tolist(),
                    coefficient_relative_error_percentiles=np.percentile(
                        z['coefficient_relative_error'], [0, 50, 90, 99, 100]).tolist())
                for prefix in ('line', 'broad'):
                    row[prefix+'_power_error_dB'] = (10*np.log10(
                        np.maximum(z[prefix+'_mean'], 1e-24)/
                        np.maximum(source[prefix+'_mean'], 1e-24))).reshape(-1, 2).tolist()
                    row[prefix+'_coherence_error'] = abs(z[prefix+'_complex_coherence']-
                        source[prefix+'_complex_coherence']).tolist()
                    row[prefix+'_CV_error'] = abs(z[prefix+'_CV']-
                        source[prefix+'_CV']).reshape(-1, 2).tolist()
                row['chunks_broad_power_error_dB'] = (10*np.log10(
                    np.maximum(z['chunks_broad_mean'], 1e-24)/
                    np.maximum(source['chunks_broad_mean'], 1e-24))).reshape(3, -1, 2).tolist()
                row['chunks_broad_coherence_error'] = abs(
                    z['chunks_broad_complex_coherence']-
                    source['chunks_broad_complex_coherence']).tolist()
                row['chunks_broad_CV_error'] = abs(z['chunks_broad_CV']-
                    source['chunks_broad_CV']).reshape(3, -1, 2).tolist()
                rows.append(row)
        solves.append(dict(label=case['label'], **case['solve']))
    assert len(rows) == 24 and len(solves) == 6
    return rows, solves, inputs


def summarize(rows, solves):
    result = dict(source_models=6, engines=1, ascents=2, in_sample_only=True,
        solver_converged=sum(s['converged'] for s in solves),
        solver_stop_codes=[s['stop'] for s in solves], variants={}, paired={})
    for name in VARIANTS:
        rr = [r for r in rows if r['variant'] == name]
        result['variants'][name] = dict(
            new_objective_mean=float(np.mean([r['new_objective'] for r in rr])),
            **{key+'_mean': float(np.mean(abs(np.array([r[key] for r in rr]))))
               for key in ERRORS},
            wave_region_NRMSE_by_region=np.mean([r['wave_region_NRMSE'] for r in rr], axis=0).tolist(),
            broad_signed_power_error_dB_by_band=np.mean([r['broad_power_error_dB']
                for r in rr], axis=(0, 2)).tolist())
    candidate = {r['label']: r for r in rows if r['variant'] == 'complete'}
    for base_name in VARIANTS[:-1]:
        comparisons = {}
        for key in ERRORS:
            delta = np.array([abs(np.asarray(candidate[r['label']][key]))-
                abs(np.asarray(r[key])) for r in rows if r['variant'] == base_name])
            comparisons[key] = dict(mean_change=float(delta.mean()),
                improved=int((delta < -1e-12).sum()), regressed=int((delta > 1e-12).sum()),
                equivalent=int((abs(delta) <= 1e-12).sum()), count=int(delta.size))
        result['paired']['complete_minus_'+base_name] = comparisons
    return result

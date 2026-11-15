"""Independently rebuild all30 publication rows, known records and regression counts."""
import argparse, os, shutil, sys
from pathlib import Path
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'study', 'known', 'review'):
        p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args()
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[name] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    from circular_phase_lift_v1.audit_oracle import statistics
    repo = Path(__file__).resolve().parents[1]
    shutil.copy2(__file__, a.review/'executed_metrics_audit.py')
    report = load(a.study/'report.json'); pub = load(a.review/'report.json')
    assert pub['result'] == 'observer_frequency_review_ready'
    for path, digest in pub['inputs'].items(): assert sha(path) == digest
    for name, digest in pub['sources'].items():
        assert sha(repo/name) == sha(a.review/'exact_sources'/name) == digest
    known = load(a.known/'report.json')
    assert load(a.review/'known_inputs.json') == known['cases']
    rows, solves, summary = (load(a.review/(name+'.json')) for name in ('figure_inputs', 'solve_inputs', 'summary'))
    tags = ('interpolated', 'old_original4000', 'old_corrected', 'complete', 'weighted')
    errors = ('wave_NRMSE', 'wave_region_NRMSE', 'line_power_error_dB',
        'broad_power_error_dB', 'line_coherence_error', 'broad_coherence_error',
        'line_CV_error', 'broad_CV_error', 'chunks_broad_power_error_dB',
        'chunks_broad_coherence_error', 'chunks_broad_CV_error')
    def close(left, right, name):
        x, y = np.asarray(left), np.asarray(right)
        assert x.shape == y.shape and np.allclose(x, y, rtol=2e-10, atol=2e-11), name
    assert len(rows) == 30 and len(solves) == 6
    oracle_rows = []
    for j, case in enumerate(report['cases']):
        folder = a.study/case['label']
        with np.load(folder/'source.npz') as z: source = {k: z[k] for k in z.files}
        slices = np.array_split(np.arange(case['source_rows']), 3)
        chunks = [statistics(source['broadband_power'][s], source['broadband_cross'][s]) for s in slices]
        for k, tag in enumerate(tags):
            saved = rows[j*5+k]
            assert saved['label'] == case['label'] and saved['variant'] == tag
            desc = case['variants'][tag]
            assert saved['root_hz'] == case['root_hz'] and saved['weighted_objective'] == desc['weighted_objective']
            with np.load(folder/desc['file']) as z:
                diff = z['audio']-source['audio']
                expected = dict(wave_NRMSE=float(np.linalg.norm(diff)/np.linalg.norm(source['audio'])),
                    wave_region_NRMSE=[float(np.linalg.norm(diff[s])/np.linalg.norm(source['audio'][s]))
                        for s in (slice(0, 2048), slice(2048, -2048), slice(-2048, None))])
                for prefix, pk, ck in (('line', 'power', 'cross'), ('broad', 'broadband_power', 'broadband_cross')):
                    origin = statistics(source[pk], source[ck]); rendered = statistics(z[pk], z[ck])
                    expected[prefix+'_power_error_dB'] = (10*(np.log10(np.maximum(rendered['mean'], 1e-24))-
                        np.log10(np.maximum(origin['mean'], 1e-24)))).reshape(-1, 2)
                    expected[prefix+'_coherence_error'] = abs(rendered['complex_coherence']-origin['complex_coherence'])
                    expected[prefix+'_CV_error'] = abs(rendered['CV']-origin['CV']).reshape(-1, 2)
                expected['chunks_broad_power_error_dB'] = []
                expected['chunks_broad_coherence_error'] = []
                expected['chunks_broad_CV_error'] = []
                for part, origin in zip(slices, chunks):
                    rendered = statistics(z['broadband_power'][part], z['broadband_cross'][part])
                    expected['chunks_broad_power_error_dB'].append((10*(np.log10(np.maximum(rendered['mean'], 1e-24))-
                        np.log10(np.maximum(origin['mean'], 1e-24)))).reshape(-1, 2))
                    expected['chunks_broad_coherence_error'].append(abs(rendered['complex_coherence']-origin['complex_coherence']))
                    expected['chunks_broad_CV_error'].append(abs(rendered['CV']-origin['CV']).reshape(-1, 2))
                for name, value in expected.items(): close(value, saved[name], (case['label'], tag, name))
                close(source['broad_mean'].reshape(-1, 2), saved['source_broad_mean'], 'source band energy')
                close(z['broad_mean'].reshape(-1, 2), saved['rendered_broad_mean'], 'rendered band energy')
                oracle_rows.append(dict(label=case['label'], variant=tag, **expected))
        assert solves[j] == dict(label=case['label'], **case['solve'])
    for tag in tags:
        rr = [r for r in oracle_rows if r['variant'] == tag]; ss = summary['variants'][tag]
        for key in errors:
            close(np.mean(abs(np.array([r[key] for r in rr]))), ss[key+'_mean'], (tag, key, 'aggregate'))
        close(np.mean([r['wave_region_NRMSE'] for r in rr], axis=0), ss['wave_region_NRMSE_by_region'], 'regions')
        close(np.mean([r['broad_power_error_dB'] for r in rr], axis=(0, 2)), ss['broad_signed_power_error_dB_by_band'], 'signed bands')
        close(np.mean([r['weighted_objective'] for r in rows if r['variant'] == tag]), ss['weighted_objective_mean'], 'objective')
    candidate = {r['label']: r for r in oracle_rows if r['variant'] == 'weighted'}
    for tag in tags[:-1]:
        for key in errors:
            delta = np.array([abs(np.asarray(candidate[r['label']][key]))-abs(np.asarray(r[key]))
                for r in oracle_rows if r['variant'] == tag])
            saved = summary['paired']['weighted_minus_'+tag][key]
            expected = dict(improved=int((delta < -1e-12).sum()), regressed=int((delta > 1e-12).sum()),
                equivalent=int((abs(delta) <= 1e-12).sum()), count=int(delta.size))
            assert all(saved[k] == v for k, v in expected.items()), (tag, key)
            close(delta.mean(), saved['mean_change'], 'paired mean')
    assert summary['solver_converged'] == sum(c['solve']['converged'] for c in report['cases'])
    assert summary['solver_stop_codes'] == [c['solve']['stop'] for c in report['cases']]
    assert (summary['source_models'], summary['engines'], summary['ascents']) == (6, 1, 2)
    result = dict(result='independent_observer_frequency_publication_passed', all30_rows_verified=True,
        all6_solver_records_verified=True, all6_known_records_exact=True,
        all_aggregates_and_improvement_regression_counts_verified=True,
        **{key+'_sha256': sha(a.review/(key+'.json')) for key in ('figure_inputs', 'solve_inputs', 'known_inputs', 'summary')},
        auditor_sha256=sha(__file__), oracle_sha256=sha(repo/'tools/circular_phase_lift_v1/audit_oracle.py'))
    save(a.review/'metrics_verification.json', result); print(result['result'], flush=True)


if __name__ == '__main__':
    main()

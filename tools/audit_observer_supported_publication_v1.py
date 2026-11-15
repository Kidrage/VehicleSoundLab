"""Verify all published numeric rows/gates/counts against independently audited results."""
import argparse, shutil
from pathlib import Path
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('study', 'review'):
        p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args()
    out = a.review/'metrics_verification.json'
    assert not out.exists()
    shutil.copy2(__file__, a.review/'executed_metrics_audit.py')
    r = dict(result='running', maximum_relative_error=0.)

    def compare(x, y, path='root'):
        if isinstance(x, dict):
            assert set(x) == set(y), path
            for key in x:
                compare(x[key], y[key], path+'/'+key)
        elif isinstance(x, list):
            assert len(x) == len(y), path
            for j, (v, w) in enumerate(zip(x, y)):
                compare(v, w, path+'/'+str(j))
        elif isinstance(x, (bool, str)):
            assert x == y, path
        elif isinstance(x, (int, float)):
            error = abs(x-y)/max(1., abs(x), abs(y))
            assert error < 2e-8, (path, error)
            r['maximum_relative_error'] = max(error, r['maximum_relative_error'])
        else:
            raise TypeError(path)

    try:
        review = load(a.review/'report.json')
        assert review['result'] == 'observer_supported_publication_ready'
        for path, digest in review['inputs'].items():
            assert sha(path) == digest
        assert sha(a.review/'figure_inputs.json') == review['figure_inputs_sha256']
        known = load(a.study/'known_audit3/report.json')
        context = load(a.study/'context_audit1/report.json')
        full = load(a.study/'full_audit1/report.json')
        null = load(a.study/'null_audit1/report.json')
        for obj, result in ((known, 'independent_observer_supported_known_passed'),
                            (context, 'independent_observer_context_known_passed'),
                            (full, 'independent_observer_supported_full_known_passed'),
                            (null, 'independent_observer_supported_null_passed')):
            assert obj['result'] == result
        rows = []
        for old, new in zip(known['cases'], context['cases']):
            assert old['label'] == new['label']
            rows.append(dict(label=old['label'], no_context_high_NRMSE=old['variants']['supported']['high_component_NRMSE'],
                context_target_high_NRMSE=new['variants']['dense']['metrics']['target_high_NRMSE'],
                context_whole_high_NRMSE=new['variants']['dense']['metrics']['whole_high_NRMSE'],
                no_context_fidelity=old['fidelity_qualified'], context_target_fidelity=new['target_fidelity_qualified']))
        source = load(a.study/'full1/report.json')
        assert full['producer_sha256'] == sha(a.study/'full1/report.json')
        bands = [dict(band=name, target=t, whole=w) for name, t, w in zip(
            ('0-3k', '3-6k', '6-8k', '8-10k', '10-14k', '14-21.6k'),
            full['metrics']['target_supported_band_complex_NRMSE'], full['metrics']['whole_supported_band_complex_NRMSE'])]
        gates = dict(gradient_ratio=full['original_space_gradient']/2e-7,
            gap_ratio=full['certificate']['gap_upper_bound']/(1e-6*full['certificate']['primal']+1e-10),
            stop=source['solver']['stop'], iterations=source['solver']['iterations'])
        nr = load(a.study/'null1/report.json')
        assert null['producer_sha256'] == sha(a.study/'null1/report.json')
        summary = dict(no_context_fidelity_passes=sum(x['no_context_fidelity'] for x in rows),
            context_target_fidelity_passes=sum(x['context_target_fidelity'] for x in rows), known_cases=8,
            full_solver_qualified=full['solver_qualified'], full_fidelity_qualified=full['fidelity_qualified'],
            full_target_wave_NRMSE=full['metrics']['target_wave_NRMSE'], maximum_target_band_NRMSE=max(x['target'] for x in bands),
            outer_loss_retained=rows[-1]['context_whole_high_NRMSE'],
            data_null_dimension_lower_bound=56448-24578, witness_data_norm=nr['witness_weighted_data_norm'],
            penalty_directional_derivative=null['penalty_directional_derivative'], native_C_or_hearing_qualified=False)
        expected = dict(sparse_rows=rows, full_band_rows=bands, gates=gates, summary=summary)
        compare(load(a.review/'figure_inputs.json'), expected)
        compare(review['summary'], summary)
        assert summary['no_context_fidelity_passes'] == 7 and summary['context_target_fidelity_passes'] == 8
        assert not summary['full_solver_qualified'] and summary['full_fidelity_qualified']
        assert summary['outer_loss_retained'] > .02
        for name, digest in review['images'].items():
            assert sha(a.review/name) == digest
        r.update(result='independent_observer_supported_publication_passed',
            all8_sparse_rows_all6_full_band_rows_and_all_gates_verified=True,
            all_counts_and_failures_verified=True, producer_sha256=sha(a.review/'report.json'),
            figure_inputs_sha256=sha(a.review/'figure_inputs.json'), auditor_sha256=sha(__file__))
        save(out, r)
        print(r['result'], flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error))
        save(out, r)
        raise


if __name__ == '__main__':
    main()

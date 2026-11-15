"""Audit every published row, solver gate and regression count against independent reports."""
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
    r = dict(result='running', maximum_scaled_error=0.)
    def compare(x, y):
        if isinstance(x, dict):
            assert x.keys() == y.keys()
            for k in x:
                compare(x[k], y[k])
        elif isinstance(x, list):
            assert len(x) == len(y)
            for v, w in zip(x, y):
                compare(v, w)
        elif isinstance(x, (str, bool)):
            assert x == y
        else:
            error = abs(x-y)/max(1., abs(x), abs(y))
            assert error < 2e-8, (x, y, error)
            r['maximum_scaled_error'] = max(error, r['maximum_scaled_error'])
    try:
        pub = load(a.review/'report.json')
        for path, digest in pub['inputs'].items():
            assert sha(path) == digest
        assert sha(a.review/'figure_inputs.json') == pub['figure_inputs_sha256']
        d = load(a.study/'algebra_audit1/report.json')
        p = load(a.study/'primal_algebra_audit1/report.json')
        c = load(a.study/'context_audit1/report.json')
        f = load(a.study/'full_audit1/report.json')
        source = load(a.study/'full1/report.json')
        assert f['producer_sha256'] == sha(a.study/'full1/report.json')
        assert d['dense_equivalence_all_qualified'] and not d['all_qualified'] and p['all_qualified'] and c['all_qualified']
        tiny = [dict(label=x['label'], failed_dual_error=x['variants']['iterative_dual']['dense_relative_error'],
            primal_error=y['variants']['iterative_primal']['dense_relative_error'], dual_pass=x['qualified'], primal_pass=y['qualified'])
            for x, y in zip(d['cases'], p['cases'])]
        context = [dict(label=v['label'], node_error=v['dense_relative_error'], qualified=v['qualified'], **v['metrics']) for v in c['cases']]
        old, new = source['old_results'], f['metrics']
        bands = [dict(band=b, old_target=ot, new_target=nt, old_whole=ow, new_whole=nw) for b, ot, nt, ow, nw in zip(
            ('0-3k', '3-6k', '6-8k', '8-10k', '10-14k', '14-21.6k'),
            old['target_supported_band_complex_NRMSE'], new['target_supported_band_complex_NRMSE'],
            old['whole_supported_band_complex_NRMSE'], new['whole_supported_band_complex_NRMSE'])]
        gates = dict(old_gradient=source['old_solver']['relative_stationarity']/2e-7,
            new_gradient=f['original_space_gradient']/2e-7,
            old_residual_gap=source['old_certificate']['gap_upper_bound']/(1e-6*source['old_certificate']['primal']+1e-10),
            new_residual_gap=f['residual_certificate']['gap_upper_bound']/(1e-6*f['residual_certificate']['primal']+1e-10),
            new_representer_gap=f['representer_certificate']['gap_upper_bound']/(1e-6*f['representer_certificate']['primal']+1e-10))
        summary = dict(dual_algebra_passes=sum(v['dual_pass'] for v in tiny), primal_algebra_passes=sum(v['primal_pass'] for v in tiny),
            actual_Hann_passes=sum(v['qualified'] for v in context), full_solver_qualified=f['solver_qualified'], full_fidelity_qualified=f['fidelity_qualified'],
            old_objective=source['old_certificate']['primal'], new_objective=f['residual_certificate']['primal'],
            old_wave=old['whole_wave_NRMSE'], new_wave=new['whole_wave_NRMSE'], old_target_wave=old['target_wave_NRMSE'], new_target_wave=new['target_wave_NRMSE'],
            target_band_regressions=sum(v['new_target'] > v['old_target'] for v in bands), whole_band_regressions=sum(v['new_whole'] > v['old_whole'] for v in bands),
            region_regressions=sum(n > o for o, n in zip(old['whole_wave_regions_NRMSE'], new['whole_wave_regions_NRMSE'])),
            old_region_errors=old['whole_wave_regions_NRMSE'], new_region_errors=new['whole_wave_regions_NRMSE'],
            original_outer_high_loss=context[-1]['whole_high_NRMSE'], null_witness_penalty_derivative=f['saved_null_witness_penalty_derivative'],
            source_or_runtime_or_hearing_qualified=False)
        compare(load(a.review/'figure_inputs.json'), dict(tiny=tiny, context=context, bands=bands, gates=gates, summary=summary))
        compare(pub['summary'], summary)
        assert (summary['dual_algebra_passes'], summary['primal_algebra_passes'], summary['actual_Hann_passes']) == (0, 4, 8)
        assert (summary['target_band_regressions'], summary['whole_band_regressions'], summary['region_regressions']) == (1, 3, 3)
        assert not summary['full_solver_qualified'] and summary['original_outer_high_loss'] > .02
        assert all(sha(a.review/name) == digest for name, digest in pub['images'].items())
        r.update(result='independent_observer_representer_review_passed', all4_tiny_all8_Hann_all6bands_all_gates_and_counts_verified=True,
            failures_and_regressions_retained=True, producer_sha256=sha(a.review/'report.json'),
            figure_inputs_sha256=sha(a.review/'figure_inputs.json'), auditor_sha256=sha(__file__))
        save(out, r)
        print(r['result'], flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error))
        save(out, r)
        raise


if __name__ == '__main__':
    main()

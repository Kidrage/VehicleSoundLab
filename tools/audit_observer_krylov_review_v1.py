"""Independently bind every plotted series and qualification count to evidence."""
import argparse, os, shutil, sys
from pathlib import Path
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'study', 'parent', 'review'):
        p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args()
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    shutil.copy2(__file__, a.review/'executed_metrics_audit.py')
    source = load(a.review/'report.json')
    for path, digest in source['inputs'].items():
        assert sha(path) == digest
    assert sha(a.review/'executed_publication.py') == source['publisher_sha256']
    assert sha(a.review/'figure_inputs.json') == source['figure_inputs_sha256']
    assert all(sha(a.review/n) == digest for n, digest in source['images'].items())
    plot = load(a.review/'figure_inputs.json')
    full = load(a.study/'full1/report.json')
    full_audit = load(a.study/'full_audit1/report.json')
    known = load(a.study/'known1/report.json')
    known_audit = load(a.study/'known_audit1/report.json')
    reorth = load(a.study/'reorth_known1/report.json')
    ra = load(a.study/'reorth_known_audit1/report.json')
    assert len(known['cases']) == len(known_audit['cases']) == 11
    assert full['info']['forward_steps'] == full_audit['cases'][0]['forward_steps'] == 128
    with np.load(a.study/'full1/coefficients.npz') as z:
        for i, name in enumerate(('U_gram', 'V_gram')):
            g = z[name]
            prefix = []
            for j in range(1, len(g)+1):
                prefix.append(max((abs(float(g[k, l])) for k in range(j) for l in range(k)), default=0.))
            assert np.max(abs(np.array(prefix)-plot['prefixes'][i])) < 1e-14
    old = load(a.parent/'primal_algebra1/report.json')['cases']
    old_h = load(a.parent/'context1/report.json')['cases']
    expected_old = [c['stats']['iterative_primal']['dense_relative_error'] for c in old]+[c['dense_relative_error'] for c in old_h]
    assert expected_old == plot['old_node_errors']
    assert len(reorth['cases']) == len(ra['cases']) == 12
    for j, (row, audit) in enumerate(zip(reorth['cases'], ra['cases'])):
        assert row['label'] == audit['label'] and row['qualified'] == audit['qualified'] == plot['qualified'][j]
        assert row['solver']['stop'] == audit['stopping_code'] == plot['stops'][j]
        assert row['dense_relative_error'] == plot['new_node_errors'][j]
        assert abs(row['dense_relative_error']-audit['dense_relative_error']) < 1e-15
        s = row['solver']
        ratio = s['transformed_normal_norm']/(s['projected_Frobenius_estimate']*s['residual_norm']*1e-11)
        assert abs(ratio-plot['direct_stop_ratio'][j]) < 1e-13
        assert audit['independent_original_dense_transformed_normal_relative']/1e-11 == plot['independent_dense_stop_ratio'][j]
    summary = dict(known_controls=11, full_probe_steps=128,
        full_U_max_offdiagonal=full['info']['U_max_offdiagonal'], full_V_max_offdiagonal=full['info']['V_max_offdiagonal'],
        reorth_cases=12, reorth_passes=sum(c['qualified'] for c in ra['cases']),
        reorth_stopping_failures=sum(c['stopping_code'] == 7 for c in ra['cases']),
        max_new_node_error=max(c['dense_relative_error'] for c in ra['cases']), full_fit_or_real_source_or_timbre_qualified=False)
    assert summary.keys() == source['summary'].keys()
    for name, value in summary.items():
        if name == 'max_new_node_error':
            assert abs(value-source['summary'][name]) < 1e-15
        else:
            assert value == source['summary'][name]
    save(a.review/'metrics_verification.json', dict(result='independent_observer_krylov_review_passed',
        summary=summary, all12_series_and_gates_verified=True, both_full_Gram_prefix_series_verified=True,
        producer_sha256=sha(a.review/'report.json'), auditor_sha256=sha(__file__)))
    print('independent_observer_krylov_review_passed', summary, flush=True)


if __name__ == '__main__':
    main()

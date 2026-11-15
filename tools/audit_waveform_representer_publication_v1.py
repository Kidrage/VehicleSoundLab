"""Recompute publication rows from bound producer/audit records, without fitting."""
import argparse
import hashlib
import json
import math
import shutil
from pathlib import Path


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def same(x, y):
    if isinstance(x, float) or isinstance(y, float):
        assert math.isclose(x, y, rel_tol=3e-14, abs_tol=1e-300), (x, y)
    else:
        assert x == y, (x, y)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('study', 'publication', 'out'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, args.out/'executed_audit.py')
    report = read(args.publication/'report.json')
    plotted = read(args.publication/'figure_inputs.json')
    assert report['figure_inputs_sha256'] == digest(args.publication/'figure_inputs.json')
    assert report['publisher_sha256'] == digest(args.publication/'executed_publication.py')
    for name, expected in report['images'].items():
        assert digest(args.publication/name) == expected
    for name, expected in report['inputs'].items():
        assert digest(name) == expected
    assert len(plotted['versions']) == 2
    versions, producer_count, explicit_count, frame_count = [], 0, 0, 0
    original_bindings, executed_bindings = {}, {}
    for number in (1, 2):
        folder = args.study/f'known{number}'
        source = read(folder/'report.json')
        audit_dir = args.study/f'known_audit{number}'
        audit = read(audit_dir/'report.json')
        assert audit['producer_sha256'] == digest(folder/'report.json')
        assert audit['auditor_sha256'] == digest(audit_dir/'executed_audit.py')
        for index, (name, expected) in enumerate(audit['oracles_sha256'].items()):
            assert digest(audit_dir/f'executed_oracle_{index}.py') == expected
        for name, expected in source['sources'].items():
            assert digest(folder/'exact_sources'/name) == expected
            executed_bindings[f'known{number}/{name}'] = expected
        for name, expected in source['inputs'].items():
            assert digest(name) == expected
            original_bindings[name] = expected
        assert source['material_read'] is False
        assert len(source['cases']) == len(audit['cases']) == len(plotted['versions'][number-1]) == 12
        rows = []
        for s, a, p in zip(source['cases'], audit['cases'], plotted['versions'][number-1]):
            assert s['label'] == a['label'] == p['label'] and s['kind'] == a['kind'] == p['kind']
            assert digest(folder/s['file']) == s['sha256']
            original = bool(a['dense_relative_error'] < 2e-7 and a['original_gradient'] < 2e-7
                            and all(v['passed'] for v in a['certificates'].values()))
            assert original == a['original_equations_and_gaps_passed']
            if number == 1:
                qualified = original and a['independent_original_direct_normal_relative'] <= 1e-11
            else:
                qualified = (original and a['original_stable_normal_relative'] <= 1e-11
                             and a['original_backward_discrepancy'] <= 1e-11
                             and s['solver']['stable_root_guard_passed'])
            assert qualified == a['qualified'] == p['qualified']
            expected = dict(kind=s['kind'], label=s['label'], dense_error=a['dense_relative_error'],
                original_direct_normal=a['independent_original_direct_normal_relative'],
                root_direct_normal=a['root_direct_normal_relative'],
                original_stable_normal=a.get('original_stable_normal_relative'),
                original_backward_discrepancy=a.get('original_backward_discrepancy'), qualified=qualified,
                all_original_equations_and_gaps_passed=original,
                metric_seconds=s['metric_build_seconds'], solve_seconds=s['root_and_solve_seconds'],
                cumulative_peak_bytes=s['process_peak_working_set_bytes'], metric_bytes=s['dense_wave_metric_bytes'],
                original_primal_condition=s['solver']['primal_augmented_condition'],
                waveform_dual_condition=s['solver']['dual_augmented_condition'])
            for tag in ('residual', 'representer'):
                c = s[tag+'_certificate']
                assert c['relative_gate'] == 1e-6 and c['absolute_gate'] == 1e-10
                ratio = c['gap_upper_bound']/(1e-6*c['primal']+1e-10)
                assert (ratio <= 1) == c['additional_gap_gate_passed']
                expected[tag+'_gap_ratio'] = ratio
            assert set(expected) == set(p)
            for name, value in expected.items():
                same(value, p[name])
            rows.append(expected)
            producer_count += 1
        versions.append(rows)
        explicit_dir = args.study/f'explicit{number}'
        explicit = read(explicit_dir/'report.json')
        ea_dir = args.study/f'explicit_audit{number}'
        ea = read(ea_dir/'report.json')
        assert ea['producer_sha256'] == digest(explicit_dir/'report.json')
        assert ea['auditor_sha256'] == digest(ea_dir/'executed_audit.py')
        assert ea['all_qualified'] and len(explicit['cases']) == len(ea['cases']) == 7
        assert len(explicit['frames']) == len(ea['frames']) == 4
        for name, expected in explicit['sources'].items():
            assert digest(explicit_dir/'exact_sources'/name) == expected
            executed_bindings[f'explicit{number}/{name}'] = expected
        for group in ('cases', 'frames'):
            for s, a in zip(explicit[group], ea[group]):
                assert s['label'] == a['label'] and a['qualified']
                assert digest(explicit_dir/s['file']) == s['sha256']
                if group == 'cases':
                    assert a['Decimal_precisions'] == [80, 110]
                    explicit_count += 1
                else:
                    assert a['all_entries'] == 41**2
                    frame_count += 1
    # Compute each individual array shape independently. These are NOT a sum
    # of live allocations or a measured peak, and no full solve is claimed.
    n, p = 12289, 49*288*2
    k = min(n, p)
    shapes = {'mono_wave_metric': (n,n), 'mono_dense_penalty': (p,p),
        'mono_penalty_Cholesky': (p,p), 'mono_weighted_Phi': (n,p),
        'mono_whitened_X': (n,p), 'mono_X_QR_storage': (n,p),
        'mono_dual_augmented_matrix': (p+k,k), 'mono_current_full_dual_Q': (p+k,p+k),
        'stereo_dense_penalty': (2*p,2*p)}
    expected_summary = dict(unique_original_cases=12, explicit_algebra_controls=7, finite_DFT_controls=4,
        before_passes=sum(r['qualified'] for r in versions[0]), after_passes=sum(r['qualified'] for r in versions[1]),
        all_original_equations_and_gaps_passed=all(r['all_original_equations_and_gaps_passed'] for r in versions[1]),
        known_dense_error_min=min(r['dense_error'] for r in versions[1]),
        known_dense_error_max=max(r['dense_error'] for r in versions[1]),
        failed_labels=[r['label'] for r in versions[1] if not r['qualified']],
        failed_original_stable_normal=[r['original_stable_normal'] for r in versions[1] if not r['qualified']],
        peak_process_bytes=max(r['cumulative_peak_bytes'] for r in versions[1]),
        full_array_bytes={name: 8*math.prod(shape) for name, shape in shapes.items()},
        full_shape_hypothesis=dict(mono_waveform_frames=n,mono_source_columns=p),
        full_runtime_or_material_qualified=False, original_stopping_and_gap_gates_unchanged=True)
    assert expected_summary == plotted['summary'] == report['summary']
    assert (expected_summary['before_passes'], expected_summary['after_passes']) == (4, 9)
    assert expected_summary['failed_labels'] == ['constant_0.01', 'constant_0.0001', 'constant_1e-05']
    result = dict(result='independent_waveform_representer_publication_verified', plotted_rows=producer_count,
        unique_original_cases=12, explicit_executions=explicit_count, finite_DFT_executions=frame_count,
        summary=expected_summary, original_input_bindings=original_bindings,
        executed_version_bindings=executed_bindings,
        producer_publication_sha256=digest(args.publication/'report.json'), auditor_sha256=digest(__file__),
        images_individually_viewed_by_agent=['known_controls.png','resource_scope.png'],
        source_audio_or_C_or_full_scale_or_SHARC_qualification=False)
    (args.out/'report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n',
                                      encoding='utf-8',newline='\n')
    print(json.dumps({k:result[k] for k in ('result','plotted_rows','explicit_executions','finite_DFT_executions')},indent=2))


if __name__ == '__main__':
    main()

"""Read-only verification of archived solver inputs, captures and executed versions."""
import argparse
import hashlib
import json
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('archive', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args()
    def read(path):
        return json.loads(path.read_text(encoding='utf-8'))
    def sha(path):
        with path.open('rb') as f:
            return hashlib.file_digest(f, 'sha256').hexdigest()
    e = a.archive/'evidence'
    validation = read(a.archive/'validation.json')
    sources = inputs = captures = executed = 0
    for folder in ('algebra2', 'primal_algebra1', 'context1', 'full1'):
        r = read(e/folder/'report.json')
        for name, digest in r['sources'].items():
            assert sha(e/folder/'exact_sources'/name) == sha(a.archive/'source'/name) == digest
            sources += 1
        for name, digest in r.get('inputs', {}).items():
            assert sha(a.archive/validation['original_input_archive_locations'][name]) == digest
            inputs += 1
        for case in r.get('cases', []):
            assert sha(e/folder/case['file']) == case['sha256']
            captures += 1
        if folder == 'full1':
            assert sha(e/folder/'capture.npz') == r['capture_sha256']
            captures += 1
    for audit, producer, script in (
            ('algebra_audit1', 'algebra2', 'tools/audit_observer_representer_known_v1.py'),
            ('primal_algebra_audit1', 'primal_algebra1', 'tools/audit_observer_representer_known_v1.py'),
            ('context_audit1', 'context1', 'tools/audit_observer_representer_context_v1.py'),
            ('full_audit1', 'full1', 'tools/audit_observer_representer_full_v1.py')):
        r = read(e/audit/'report.json')
        assert r['result'].startswith('independent_') and r['result'].endswith('_passed')
        assert sha(e/producer/'report.json') == r['producer_sha256']
        assert sha(e/audit/'executed_audit.py') == sha(a.archive/'source'/script) == r['auditor_sha256']
        executed += 1
        for j, (name, digest) in enumerate(r.get('oracles_sha256', {}).items()):
            assert sha(e/audit/f'executed_oracle_{j}.py') == sha(a.archive/'source'/name) == digest
            executed += 1
        for name, digest in r.get('extra_inputs', {}).items():
            assert sha(a.archive/validation['original_input_archive_locations'][name]) == digest
            inputs += 1
    failed = read(e/'algebra1/report.json')
    assert failed['result'] == 'failed' and 'no setter' in failed['error']
    for name, digest in failed['sources'].items():
        assert sha(e/'algebra1/exact_sources'/name) == digest
    dual = read(e/'algebra2/report.json')
    assert len(dual['cases']) == 4 and all(not c['qualified'] for c in dual['cases'])
    assert read(e/'primal_algebra1/report.json')['all_qualified']
    assert read(e/'context1/report.json')['all_qualified']
    for folder in ('review1', 'review2'):
        r = read(e/folder/'report.json')
        assert sha(e/folder/'executed_publication.py') == r['publisher_sha256']
        assert sha(e/folder/'figure_inputs.json') == r['figure_inputs_sha256']
        assert all(sha(e/folder/name) == digest for name, digest in r['images'].items())
        for name, digest in r['inputs'].items():
            relative = Path(name).relative_to(Path(next(iter(r['inputs']))).parent.parent)
            assert sha(e/relative) == digest
        audit = read(e/folder/'metrics_verification.json')
        assert sha(e/folder/'executed_metrics_audit.py') == audit['auditor_sha256']
        assert sha(e/folder/'report.json') == audit['producer_sha256']
    full = read(e/'full_audit1/report.json')
    assert full['solver_qualified'] is False and full['fidelity_qualified'] is True
    visual = read(e/'review2/visual_review.json')
    assert visual['accepted_for_publication'] and visual['scientific_figures_individually_viewed'] == 2
    assert visual['images_sha256'] == read(e/'review2/report.json')['images']
    r = dict(result='independent_observer_representer_input_executed_capture_bindings_verified',
        producer_source_bindings=sources, original_input_bindings=inputs, capture_bindings=captures,
        passing_executed_auditor_oracle_bindings=executed, construction_failure_preserved=True,
        dual_four_failures_preserved=True, layout_versions_preserved=2, full288_failure_preserved=True,
        auditor_sha256=sha(Path(__file__)))
    a.out.write_text(json.dumps(r, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
    print(json.dumps(r, ensure_ascii=False))


if __name__ == '__main__':
    main()

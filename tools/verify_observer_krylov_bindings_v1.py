"""Read-only source/input/capture/executed bindings, including failed gates."""
import argparse, hashlib, json
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
    for folder in ('known1', 'full1', 'reorth_known1'):
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
        for name, digest in r.get('files', {}).items():
            assert sha(e/folder/name) == digest
            captures += 1
    for folder, producer, script in (('known_audit1', 'known1', 'tools/audit_observer_krylov_v1.py'),
            ('full_audit1', 'full1', 'tools/audit_observer_krylov_v1.py'),
            ('reorth_known_audit1', 'reorth_known1', 'tools/audit_observer_reorth_known_v1.py')):
        r = read(e/folder/'report.json')
        assert r['result'].startswith('independent_') and r['result'].endswith('_passed')
        assert r['producer_sha256'] == sha(e/producer/'report.json')
        assert r['auditor_sha256'] == sha(e/folder/'executed_audit.py') == sha(a.archive/'source'/script)
        executed += 1
        for j, (name, digest) in enumerate(r.get('oracles_sha256', {}).items()):
            assert sha(e/folder/f'executed_oracle_{j}.py') == sha(a.archive/'source'/name) == digest
            executed += 1
    full = read(e/'full_audit1/report.json')
    assert full['all128_forward_and_adjoint_recurrences_verified']
    cases = read(e/'reorth_known_audit1/report.json')['cases']
    assert len(cases) == 12 and sum(c['qualified'] for c in cases) == 4
    assert all(c['stopping_code'] == 7 and not c['qualified'] for c in cases if c['kind'] == 'Hann')
    for folder in ('review1', 'review2'):
        r = read(e/folder/'report.json')
        assert sha(e/folder/'executed_publication.py') == r['publisher_sha256']
        assert sha(e/folder/'figure_inputs.json') == r['figure_inputs_sha256']
        assert all(sha(e/folder/n) == d for n, d in r['images'].items())
        for name, digest in r['inputs'].items():
            assert sha(a.archive/validation['original_input_archive_locations'][name]) == digest
            inputs += 1
        audit = read(e/folder/'metrics_verification.json')
        assert sha(e/folder/'executed_metrics_audit.py') == audit['auditor_sha256']
        assert sha(e/folder/'report.json') == audit['producer_sha256']
        failed = read(e/folder/'failed_metrics_audit_1.json')
        assert failed['result'] == 'failed' and abs(failed['difference']) < 1e-15
        assert sha(e/folder/'failed_metrics_audit_1.py') != audit['auditor_sha256']
    visual = read(e/'review2/visual_review.json')
    assert visual['accepted_for_publication'] and visual['scientific_figures_individually_viewed'] == 2
    assert visual['images_sha256'] == read(e/'review2/report.json')['images']
    result = dict(result='independent_observer_krylov_input_executed_capture_bindings_verified',
        producer_source_bindings=sources, original_input_bindings=inputs, capture_bindings=captures,
        executed_auditor_oracle_bindings=executed, full128_verified=True, eight_Hann_failures_preserved=True,
        failed_publication_audits_preserved=2, layout_versions_preserved=2, auditor_sha256=sha(Path(__file__)))
    a.out.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()

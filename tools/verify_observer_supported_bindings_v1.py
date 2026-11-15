"""Read-only binding check of frozen known observations, inputs and executed versions."""
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
    for folder in ('known1', 'context1', 'full1', 'null1'):
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
        if folder == 'known1':
            for name in ('metric_controls', 'stereo_controls'):
                assert sha(e/folder/(name+'.npz')) == r[name+'_sha256']
                captures += 1
            for control in r['controls']:
                if 'file' in control:
                    assert sha(e/folder/control['file']) == control['sha256']
                    captures += 1
        if folder in ('full1', 'null1'):
            name, field = ('capture.npz', 'capture_sha256') if folder == 'full1' else ('witness.npz', 'witness_sha256')
            assert sha(e/folder/name) == r[field]
            captures += 1
    for audit, producer in (('known_audit3', 'known1'), ('context_audit1', 'context1'), ('full_audit1', 'full1'), ('null_audit1', 'null1')):
        r = read(e/audit/'report.json')
        assert sha(e/producer/'report.json') == r['producer_sha256']
        assert sha(e/audit/'executed_audit.py') == r['auditor_sha256']
        executed += 1
        for j, (name, digest) in enumerate(r.get('oracles_sha256', {}).items()):
            assert sha(e/audit/f'executed_oracle_{j}.py') == sha(a.archive/'source'/name) == digest
            executed += 1
    for name in ('known_audit1', 'known_audit2'):
        assert read(e/name/'report.json')['result'] == 'failed'
        assert (e/name/'executed_audit.py').is_file()
    for name in ('review1', 'review2'):
        r = read(e/name/'report.json')
        assert sha(e/name/'executed_publication.py') == r['publisher_sha256']
        assert sha(e/name/'figure_inputs.json') == r['figure_inputs_sha256']
        assert all(sha(e/name/image) == digest for image, digest in r['images'].items())
    pub = read(e/'review2/metrics_verification.json')
    assert sha(e/'review2/executed_metrics_audit.py') == pub['auditor_sha256']
    assert sha(e/'review2/report.json') == pub['producer_sha256']
    assert read(e/'full_audit1/report.json')['solver_qualified'] is False
    r = dict(result='independent_observer_supported_input_executed_capture_bindings_verified',
        producer_source_bindings=sources, original_input_bindings=inputs, capture_bindings=captures,
        passing_executed_auditor_oracle_bindings=executed, failed_audits_preserved=2,
        layout_versions_preserved=2, full288_failure_preserved=True, auditor_sha256=sha(Path(__file__)))
    a.out.write_text(json.dumps(r, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
    print(json.dumps(r, ensure_ascii=False))


if __name__ == '__main__':
    main()

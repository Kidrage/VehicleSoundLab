"""Independent archive bytes, source ZIP, input identities and failure audit."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import zipfile


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for key in ('root', 'out'):
        p.add_argument('--'+key, type=Path, required=True)
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, a.out/'executed_audit.py')
    rows = read(a.root/'manifest.json')
    expected = {row['path'] for row in rows['files']}
    actual = {path.relative_to(a.root).as_posix() for path in a.root.rglob('*')
        if path.is_file() and path != a.root/'manifest.json'}
    assert actual == expected and len(expected) == len(rows['files']) == rows['file_count']
    assert sum(row['bytes'] for row in rows['files']) == rows['bytes']
    for row in rows['files']:
        path = a.root/row['path']
        assert path.resolve().is_relative_to(a.root.resolve())
        assert path.stat().st_size == row['bytes'] and digest(path) == row['sha256']
    source = {name[7:] for name in expected if name.startswith('source/')}
    with zipfile.ZipFile(a.root/'source.zip') as archive:
        assert set(archive.namelist()) == source
        for name in source:
            assert hashlib.sha256(archive.read(name)).hexdigest() == digest(a.root/'source'/name)
    proof = read(a.root/'validation.json')
    for original, archived in proof['input_archive_locations'].items():
        assert digest(original) == digest(a.root/'inputs'/archived)
    spec_path = next(path for path in (a.root/'inputs').rglob('run_spec.json')
        if 'waveform_file_real_v1' in path.parts)
    spec = read(spec_path)
    assert len(spec['sources']) == 96 and len(spec['inputs']) == 71
    repo = Path(__file__).resolve().parents[1]
    for name, wanted in spec['sources'].items():
        assert digest(a.root/'source'/name) == digest(repo/name) == wanted
    for name, wanted in spec['inputs'].items():
        assert digest(name) == wanted
    for filename, count in (('C_files_sha256.json', 670), ('voice_files_sha256.json', 82), ('F2_files_sha256.json', 3)):
        values = read(a.root/'evidence'/filename)
        assert len(values) == count
        for name, wanted in values.items():
            assert digest(repo/name) == wanted
    assert digest(repo/'handoff/C文件索引.csv') == proof['protected_C_index_sha256']
    assert not any(name.endswith('.bin') for name in expected)
    for label in ('review_audit1', 'review_audit2'):
        assert read(a.root/'evidence'/label/'report.json')['result'] == 'failed'
    assert read(a.root/'evidence/audit1/report.json')['verification_passed']
    publication = read(a.root/'evidence/review_audit3/report.json')
    assert publication['all_publication_fields_verified'] and len(publication['checks']) == 111
    assert publication['producer_sha256'] == digest(a.root/'evidence/review1/report.json')
    assert proof['source_solver_qualified'] and not proof['source_fidelity_qualified']
    assert not proof['eligible_for_later_source_statistics']
    assert proof['original_gates_unchanged'] and proof['source_resampling_tail_hypothesis_not_yet_qualified']
    result = dict(result='independent_native_error_archive_verified',
        manifest_sha256=digest(a.root/'manifest.json'), files=rows['file_count'], bytes=rows['bytes'],
        all_bytes_ZIP_and_input_bindings_verified=True, original96sources71inputs_unchanged=True,
        protected670C_H82voice3F2_and_index_unchanged=True,
        original_fidelity_failure_and_all_failed_audits_retained=True,
        full_goal_not_completed=True, auditor_sha256=digest(__file__))
    (a.out/'report.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8', newline='\n')
    print(result['result'], rows['file_count'], flush=True)


if __name__ == '__main__':
    main()

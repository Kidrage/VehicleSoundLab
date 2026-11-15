"""Independent bytes/ZIP/input/qualification check of the first-case archive."""
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
    p.add_argument('--workspace', type=Path, required=True)
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, a.out/'executed_audit.py')
    manifest = read(a.root/'manifest.json')
    rows = manifest['files']
    expected = {row['path'] for row in rows}
    actual = {p.relative_to(a.root).as_posix() for p in a.root.rglob('*')
              if p.is_file() and p != a.root/'manifest.json'}
    assert len(rows)==len(expected)==manifest['file_count'] and expected==actual
    assert sum(row['bytes'] for row in rows)==manifest['bytes']
    for row in rows:
        path = a.root/row['path']
        assert path.resolve().is_relative_to(a.root.resolve())
        assert path.stat().st_size==row['bytes'] and digest(path)==row['sha256']
    source = {path[len('source/'):] for path in expected if path.startswith('source/')}
    with zipfile.ZipFile(a.root/'source.zip') as archive:
        assert set(archive.namelist())==source
        for name in archive.namelist():
            assert hashlib.sha256(archive.read(name)).hexdigest()==digest(a.root/'source'/name)
    proof = read(a.root/'validation.json')
    for original, archived in proof['input_archive_locations'].items():
        assert digest(original)==digest(a.root/'inputs'/archived)
    spec = read(a.root/'inputs/original_producer/run_spec.json')
    assert len(spec['sources'])==96 and len(spec['inputs'])==71
    for name, expected_hash in spec['sources'].items():
        assert digest(a.root/'source'/name)==expected_hash
    assert proof['independent_mathematical_verification'] and proof['source_solver_qualified']
    assert not proof['source_fidelity_qualified'] and not proof['eligible_for_later_source_statistics']
    assert proof['native16_32_convergence_passed'] and proof['all_original_gates_unchanged']
    assert not any(path.endswith('.bin') for path in expected)
    assert read(a.root/'inputs/original_failed_audit/report.json')['result']=='failed'
    for tag in ('diagnosis1', 'diagnosis2', 'review1', 'review2', 'review3',
                'review_audit1', 'review_audit2', 'review_audit3'):
        assert (a.root/'evidence'/tag/'report.json').is_file()
    assert read(a.root/'evidence/native1/report.json')['result']=='terminal_single_case_diagnostics_verified'
    repo = Path(__file__).resolve().parents[1]
    for filename, count in (('C_files_sha256.json', 670), ('voice_files_sha256.json', 82), ('F2_files_sha256.json', 3)):
        values = read(a.root/'evidence'/filename)
        assert len(values)==count
        for name, expected_hash in values.items():
            assert digest(repo/name)==expected_hash
    result = dict(result='independent_first_actual_archive_verified', manifest_sha256=digest(a.root/'manifest.json'),
        files=len(rows), bytes=manifest['bytes'], all_bytes_and_ZIP_verified=True,
        original_input_bindings_verified=len(proof['input_archive_locations']),
        original96sources_unchanged=True, protected_C_voice_F2_unchanged=True,
        original_fidelity_failure_retained=True, all_executed_attempts_retained=True,
        no_factor_files_copied=True, no_sound_or_goal_completion_claim=True,
        auditor_sha256=digest(__file__))
    (a.out/'report.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8', newline='\n')
    print(result['result'], len(rows), flush=True)


if __name__ == '__main__':
    main()

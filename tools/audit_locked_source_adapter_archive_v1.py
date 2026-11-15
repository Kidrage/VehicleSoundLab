"""Independent terminal adapter archive bytes, source ZIP and qualification scope."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import zipfile


def digest(path):
    with Path(path).open('rb') as stream: return hashlib.file_digest(stream, 'sha256').hexdigest()


def read(path): return json.loads(Path(path).read_text(encoding='utf-8'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('root', 'out'): parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args(); args.out.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, args.out/'executed_audit.py')
    manifest = read(args.root/'manifest.json')
    expected = {row['path'] for row in manifest['files']}
    # Nested upstream manifests are regular bound inputs, not the root manifest.
    actual = {path.relative_to(args.root).as_posix() for path in args.root.rglob('*') if path.is_file() and path != args.root/'manifest.json'}
    assert expected == actual and len(expected) == manifest['file_count']
    assert sum(row['bytes'] for row in manifest['files']) == manifest['bytes']
    for row in manifest['files']:
        path = args.root/row['path']; assert path.resolve().is_relative_to(args.root.resolve())
        assert path.stat().st_size == row['bytes'] and digest(path) == row['sha256']
    names = {path[7:] for path in expected if path.startswith('source/')}
    with zipfile.ZipFile(args.root/'source.zip') as archive:
        assert set(archive.namelist()) == names
        for name in names: assert hashlib.sha256(archive.read(name)).hexdigest() == digest(args.root/'source'/name)
    proof = read(args.root/'validation.json')
    for original, relative in proof['input_archive_locations'].items():
        assert digest(original) == digest(args.root/'inputs'/relative)
    repo = Path(__file__).resolve().parents[1]
    original_spec = next(Path(name) for name in proof['input_archive_locations']
        if Path(name).name == 'run_spec.json' and Path(name).parent.name == 'real1'
        and Path(name).parent.parent.name == 'waveform_file_real_v1')
    original = read(original_spec)
    assert len(original['sources']) == 96 and len(original['inputs']) == 71
    for name, wanted in original['sources'].items(): assert digest(repo/name) == wanted
    for name, wanted in original['inputs'].items(): assert digest(name) == wanted
    for filename, count in (('C_files_sha256.json', 670), ('voice_files_sha256.json', 82), ('F2_files_sha256.json', 3)):
        values = read(args.root/'evidence'/filename); assert len(values) == count
        for name, wanted in values.items(): assert digest(repo/name) == wanted
    assert digest(repo/'handoff/C文件索引.csv') == proof['protected_C_index_sha256']
    assert all(digest(repo/name) == wanted for name, wanted in proof['protected_hearings_sha256'].items())
    for producer, auditor, count in (('known1', 'known_audit1', 4), ('prepare1', 'prepare_audit1', 5)):
        source, audit = read(args.root/'evidence'/producer/'report.json'), read(args.root/'evidence'/auditor/'report.json')
        assert audit['all_qualified'] and len(audit['cases']) == count
        assert audit['producer_sha256'] == digest(args.root/'evidence'/producer/'report.json')
        for name, wanted in source['sources'].items(): assert digest(repo/name) == wanted
    assert proof['real_result_not_qualified_by_this_archive'] and proof['no_source_or_C_or_hearing_promotion']
    assert proof['original_first_case_never_refit'] and proof['original_jobs_never_restarted']
    assert digest(args.root/'evidence/real_launch_spec.json') == proof['real_launch_spec_sha256']
    assert not any('/real1/' in name and name.startswith('evidence/') for name in expected)
    result = dict(result='independent_locked_source_adapter_archive_verified',
        manifest_sha256=digest(args.root/'manifest.json'), files=manifest['file_count'], bytes=manifest['bytes'],
        all_bytes_ZIP_inputs_and_protected_files_verified=True, real_result_not_qualified=True,
        full_goal_not_completed=True, auditor_sha256=digest(__file__))
    (args.out/'report.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8', newline='\n')
    print(result['result'], result['files'], flush=True)


if __name__ == '__main__': main()

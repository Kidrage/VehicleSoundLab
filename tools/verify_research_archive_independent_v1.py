"""Read-only archive/ZIP/current-contract verification, independent of packager."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('archive', 'summary', 'repo', 'out'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    def digest(path):
        with path.open('rb') as stream:
            return hashlib.file_digest(stream, 'sha256').hexdigest()
    def read(path):
        return json.loads(path.read_text(encoding='utf-8'))
    manifest = read(args.archive/'manifest.json')
    summary = read(args.summary)
    assert digest(args.archive/'manifest.json') == summary['manifest_sha256']
    entries = {row['path']:row for row in manifest['files']}
    actual = {p.relative_to(args.archive).as_posix() for p in args.archive.rglob('*')
              if p.is_file() and p != args.archive/'manifest.json'}
    assert len(entries) == len(manifest['files']) == manifest['file_count'] == summary['file_count']
    assert actual == entries.keys()
    total = 0
    for name, row in entries.items():
        path = args.archive/name
        assert path.resolve().is_relative_to(args.archive.resolve())
        assert path.stat().st_size == row['bytes'] and digest(path) == row['sha256'], name
        total += path.stat().st_size
    assert total == manifest['bytes'] == summary['bytes']
    source = {name.removeprefix('source/'): row['sha256'] for name, row in entries.items() if name.startswith('source/')}
    with zipfile.ZipFile(args.archive/'source.zip') as archive:
        assert len(archive.namelist()) == len(set(archive.namelist()))
        assert set(archive.namelist()) == source.keys()
        assert all(hashlib.sha256(archive.read(name)).hexdigest() == expected for name, expected in source.items())
    protected = {}
    for name, count in [('C_files_sha256.json', 670), ('voice_files_sha256.json', 82), ('F2_files_sha256.json', 3)]:
        values = read(args.archive/'evidence'/name)
        assert len(values) == count
        assert all(digest(args.repo/path) == source[path] == expected for path, expected in values.items())
        protected[name] = count
    current = set()
    for flags in (['ls-files', '-z'], ['ls-files', '--others', '--exclude-standard', '-z']):
        current.update(subprocess.check_output(['git']+flags, cwd=args.repo).decode('utf-8').split('\0'))
    assert {name for name in current if Path(name).suffix in ('.c', '.h')} == set(read(args.archive/'evidence/C_files_sha256.json'))
    assert digest(args.repo/'handoff/C文件索引.csv') == source['handoff/C文件索引.csv']
    assert all(digest(args.repo/name) == expected for name, expected in summary.get('protected_hearings_sha256', {}).items())
    result = dict(result='independent_archive_source_zip_contracts_verified', file_count=len(entries),
                  bytes=total, manifest_sha256=digest(args.archive/'manifest.json'),
                  source_zip_members=len(source), protected_current_contracts=protected,
                  C_index_exact=True, protected_hearings_exact=True, auditor_sha256=digest(Path(__file__)))
    args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False)+'\n', encoding='utf-8', newline='\n')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()

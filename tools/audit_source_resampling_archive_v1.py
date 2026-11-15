"""Independent source-transfer archive bytes, ZIP, input and scope check."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import zipfile


def digest(path):
    with Path(path).open('rb') as f: return hashlib.file_digest(f, 'sha256').hexdigest()


def read(path): return json.loads(Path(path).read_text(encoding='utf-8'))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for key in ('root', 'out'): p.add_argument('--'+key, type=Path, required=True)
    a = p.parse_args(); a.out.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, a.out/'executed_audit.py')
    manifest = read(a.root/'manifest.json')
    expected = {row['path'] for row in manifest['files']}
    actual = {p.relative_to(a.root).as_posix() for p in a.root.rglob('*') if p.is_file() and p != a.root/'manifest.json'}
    assert expected == actual and len(expected) == len(manifest['files']) == manifest['file_count']
    assert sum(row['bytes'] for row in manifest['files']) == manifest['bytes']
    for row in manifest['files']:
        path = a.root/row['path']; assert path.resolve().is_relative_to(a.root.resolve())
        assert path.stat().st_size == row['bytes'] and digest(path) == row['sha256']
    names = {name[7:] for name in expected if name.startswith('source/')}
    with zipfile.ZipFile(a.root/'source.zip') as archive:
        assert set(archive.namelist()) == names
        for name in names: assert hashlib.sha256(archive.read(name)).hexdigest() == digest(a.root/'source'/name)
    proof = read(a.root/'validation.json')
    for original, archived in proof['input_archive_locations'].items(): assert digest(original) == digest(a.root/'inputs'/archived)
    repo = Path(__file__).resolve().parents[1]
    spec = read(next(p for p in (a.root/'inputs').rglob('run_spec.json') if 'waveform_file_real_v1' in p.parts))
    assert len(spec['sources']) == 96 and len(spec['inputs']) == 71
    for name, wanted in spec['sources'].items(): assert digest(repo/name) == digest(a.root/'source'/name) == wanted
    for name, wanted in spec['inputs'].items(): assert digest(name) == wanted
    for filename, count in (('C_files_sha256.json', 670), ('voice_files_sha256.json', 82), ('F2_files_sha256.json', 3)):
        values = read(a.root/'evidence'/filename); assert len(values) == count
        for name, wanted in values.items(): assert digest(repo/name) == wanted
    assert digest(repo/'handoff/C文件索引.csv') == proof['protected_C_index_sha256']
    for folder, count in (('known_audit1', 8), ('real_audit1', 6)):
        audit = read(a.root/'evidence'/folder/'report.json')
        assert audit['verification_passed'] and len(audit['cases']) == count
    audit = read(a.root/'evidence/review_audit1/report.json')
    assert audit['verification_passed'] and audit['numeric_checks'] == 88 and audit['all_18_radius_pairs_verified']
    assert proof['saved_fit_cross_reference_complex_NRMSE']['sinc128'][-1] > proof['saved_fit_cross_reference_complex_NRMSE']['legacy'][-1]
    assert not proof['original_source_fidelity_qualified'] and not proof['eligible_for_later_source_statistics']
    assert not any(name.endswith('.bin') for name in expected)
    result = dict(result='independent_source_resampling_archive_verified',
        manifest_sha256=digest(a.root/'manifest.json'), files=manifest['file_count'], bytes=manifest['bytes'],
        all_bytes_ZIP_inputs_and_protected_files_verified=True, original_failure_and_new_cross_reference_regression_retained=True,
        original96sources71inputs_unchanged=True, full_goal_not_completed=True, auditor_sha256=digest(__file__))
    (a.out/'report.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8', newline='\n')
    print(result['result'], result['files'], flush=True)


if __name__ == '__main__': main()

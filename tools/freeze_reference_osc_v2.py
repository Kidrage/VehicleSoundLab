"""Freeze this independent OSC preview; never modifies an existing snapshot."""
from runtime_review import ROOT, sha
import json
import shutil


def main():
    source = ROOT/'references/analysis/reference_osc_v2'
    destination = ROOT/'baselines/reference_osc_v2'
    if destination.exists():
        raise SystemExit('Preserve frozen reference_osc_v2; use a new version.')
    verification = json.loads((source/'verification.json').read_text(encoding='utf-8'))
    assert verification['result'] == 'pass'
    for name, digest in verification['source_hashes'].items():
        assert sha(ROOT/name) == digest, name
    for name, digest in verification['artifacts'].items():
        assert sha(source/name) == digest, name
    for name, digest in verification['binaries'].items():
        assert sha(ROOT/'build-reference-osc-v2/Release'/name) == digest, name
    destination.mkdir()
    def copy(path, target=None):
        path = ROOT/path
        relative = path.relative_to(ROOT) if target is None else target
        dest = destination/relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)
    for name in verification['source_hashes']:
        copy(name)
    for name in verification['binaries']:
        copy('build-reference-osc-v2/Release/'+name, 'bin/'+name)
    for path in sorted(source.iterdir()):
        if path.is_file():
            copy(path.relative_to(ROOT), 'review/'+path.name)
    copy('AGENTS.md')
    files = [dict(path=str(p.relative_to(destination)).replace('\\', '/'), sha256=sha(p))
        for p in sorted(destination.rglob('*')) if p.is_file()]
    manifest = dict(version='reference_osc_v2', application='Independent reference64 preview',
        accepted='Original64OSC timbre baseline only', high_and_pitch_subjectively_accepted=False,
        native_driving_release='0.20.0 unchanged',
        scope='Six-second coefficient trajectory, not arbitrary sustained RPM/load synthesis.',
        previous_snapshot_manifests=verification['old_snapshot_manifests'],
        previous_snapshot_files_verified=verification['old_snapshot_files'], files=files)
    (destination/'manifest.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding='utf-8')
    for item in files:
        assert sha(destination/item['path']) == item['sha256']
    print(f'Frozen reference_osc_v2: {len(files)} files. Original64 accepted; high/pitch listening pending. Broad goal incomplete.')


if __name__ == '__main__':
    main()

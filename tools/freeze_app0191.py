"""Freeze the app-only maintenance release with its compatible DSP019 evidence."""
import json
import shutil
from runtime_review import ROOT, sha


def main():
    out = ROOT/'baselines/app0.19.1'
    rendered = ROOT/'renders/app0.19.1'
    if out.exists():
        raise SystemExit('Preserve completed app0.19.1.')
    check = json.loads((rendered/'verification.json').read_text(encoding='utf-8'))
    assert check['result'] == 'pass' and check['app'] == '0.19.1' and check['dsp'] == '0.19.0'
    assert check['ctest_count'] == 22
    for name, digest in check['original_source_files_preserved'].items():
        assert sha(ROOT/name) == digest, name
    for name, identities in check['intentional_app_only_changes'].items():
        assert sha(ROOT/name) == identities['new'], name
    for name, digest in check['new_sources'].items():
        assert sha(ROOT/name) == digest, name
    for name, digest in check['files'].items():
        assert sha(rendered/name) == digest, name
    for name, digest in check['binaries'].items():
        assert sha(ROOT/'build-app0191/Release'/name) == digest, name
    for name, digest in check['previous_binaries'].items():
        assert sha(ROOT/'build-v019/Release'/name) == digest, name
    for name, digest in check['previous_snapshot_manifest_identities'].items():
        assert sha(ROOT/'baselines'/name/'manifest.json') == digest, name
    legacy = ROOT/'experiments/ui_display_v1/legacy_sandbox'
    for name, digest in check['legacy_sandbox_files'].items():
        assert sha(legacy/name) == digest, name
    deliverables = ['README.md', 'AGENTS.md', 'build.ps1', 'CMakeLists.txt',
        'Launch-current.cmd', 'Launch-ui.cmd', 'Launch-v019.cmd', 'Launch-main-pressure.cmd',
        'research/App0191键盘与界面核查.md', 'research/goal_progress_app0191.json',
        'tools/verify_app0191.py', 'tools/freeze_app0191.py', 'tools/runtime_review.py', 'tools/review_audit.py']
    out.mkdir()
    def copy(source, destination):
        target = out/destination
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    for folder in ['src', 'tests']:
        shutil.copytree(ROOT/folder, out/folder)
    for name in deliverables:
        copy(ROOT/name, name)
    for name in check['binaries']:
        copy(ROOT/'build-app0191/Release'/name, 'bin/'+name)
    for path in rendered.iterdir():
        if path.is_file() and path.suffix in ['.json', '.png', '.ini', '.log', '.csv', '.vsltake']:
            copy(path, 'review/'+path.name)
    for name in ['ui_ready.png', 'ui_smoke.json']:
        copy(legacy/'renders/v0.19.0'/name, 'review/legacy_visible_'+name)
    files = [dict(path=p.relative_to(out).as_posix(), sha256=sha(p))
        for p in sorted(out.rglob('*')) if p.is_file()]
    manifest = dict(application='0.19.1', DSP='0.19.0', seed=48271,
        status='App-only hotkey repair and diagnostic capture fix; DSP019 take compatibility verified. No new sonic acceptance. Broad goal active.',
        report='research/App0191键盘与界面核查.md', previous_snapshot_manifest_identities=check['previous_snapshot_manifest_identities'],
        media='Reference media and full renders remain at workspace paths; not duplicated here.', files=files)
    (out/'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    for item in files:
        assert sha(out/item['path']) == item['sha256'], item['path']
    print(f'Frozen app0.19.1: {len(files)} files verified; DSP0.19.0 compatible. Broad goal remains active.')


if __name__ == '__main__':
    main()

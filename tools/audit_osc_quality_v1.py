"""Audit existing evidence and freeze this isolated quality experiment.

Does not rerender or alter any historical audio, native sources, or snapshots.
Large4x intermediates stay in the workspace and receive hashes in the report.
"""
from pathlib import Path
import hashlib
import json
import shutil
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'references/analysis/osc_quality_v1'
SNAPSHOT = ROOT/'baselines/osc_quality_v1'


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1024*1024), b''):
            digest.update(block)
    return digest.hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def main():
    if SNAPSHOT.exists():
        raise SystemExit('Preserve the frozen quality snapshot; choose a new version.')
    report = read(OUT/'results.json')
    refined = read(OUT/'refinement/results.json')
    c = read(OUT/'refinement/c_verification.json')
    browser = read(OUT/'browser_qa.json')
    previous = read(ROOT/'references/analysis/reference_osc_v2/verification.json')
    snapshots, checked_files = {}, 0
    expected_manifests = dict(previous['old_snapshot_manifests'])
    expected_manifests['reference_osc_v2'] = report['preserved_before']['baselines\\reference_osc_v2\\manifest.json']
    for manifest in sorted((ROOT/'baselines').glob('*/manifest.json')):
        assert sha(manifest) == expected_manifests[manifest.parent.name], manifest
        items = read(manifest)['files']
        for item in items:
            assert sha(manifest.parent/item['path']) == item['sha256'], (manifest, item['path'])
        checked_files += len(items)
        snapshots[manifest.parent.name] = sha(manifest)
    assert len(snapshots) == 40 and checked_files == 5720
    native = [v for v in read(ROOT/'baselines/v0.20.0/manifest.json')['files']
              if v['path'].replace('\\', '/').startswith(('src/', 'tests/'))]
    assert len(native) == 170
    for item in native:
        assert sha(ROOT/item['path']) == item['sha256'], item['path']
    for path, expected in previous['source_hashes'].items():
        assert sha(ROOT/path) == expected, path
    for path, expected in report['preserved_before'].items():
        assert sha(ROOT/path) == expected == report['preserved_after'][path], path
    probe = ROOT/'build-reference-osc-v1/Release/reference_osc_probe.exe'
    assert sha(probe) == c['probe_sha256']
    assert sha(OUT/'refinement/joint64.model') == c['model_sha256']
    assert sha(OUT/'refinement/joint64_c_audition.wav') == c['audition_sha256']
    for item in report['audition']['files'].values():
        assert sha(OUT/item['file']) == item['sha256'], item
    assert c['result'] == 'pass' and c['phase_stride_exact']
    assert c['max_C_float_error'] < 1e-7 and c['max_audition_pcm24_error'] <= 1/8388608
    assert c['alias_4x_difference_db'] < -100 and report['aliasing']['difference_to_native_db'] < -100
    assert refined['fit']['long_frequencies_unchanged']
    assert refined['residual_db'] < report['variants']['legacy64']['residual_db']-6
    assert browser['loads'] == 7 and browser['errors'] == []
    assert all(browser[k] for k in ['muted', 'http_and_file', 'position_and_playback_preserved',
                                   'exterior_jump', 'active_button_stable', 'narrow_viewport'])
    statuses = {}
    for name in ['OSC质感诊断V1.html', 'OSC质感诊断V1.md']:
        url = 'http://127.0.0.1:8789/research/'+urllib.parse.quote(name)
        with urllib.request.urlopen(url, timeout=10) as response:
            assert response.status == 200
            statuses[name] = response.status
    evidence = {str(p.relative_to(ROOT)): sha(p) for p in sorted(OUT.rglob('*')) if p.is_file()
                and p.name != 'verification.json'}
    verification = dict(result='pass', scope='Existing technical controls and immutable-artifact audit; no human listening acceptance.',
        old_snapshot_manifests=snapshots, old_snapshot_files=checked_files,
        unchanged_native_source_tests=len(native), native_DSP020_changed=False,
        previous_preview_source_unchanged=True, protected_originals=report['preserved_after'],
        c_verification=c, browser=browser, http=statuses, evidence_sha256=evidence,
        broad_native_tests_rerun=False, reason='Native driving code and audio backend unchanged.',
        candidate_subjectively_accepted=False, high_tuning_deferred=True)
    (OUT/'verification.json').write_text(json.dumps(verification, indent=2, ensure_ascii=False), encoding='utf-8')
    # Preserve code, reports, coefficient model and listening files. Source media
    # and installed Python packages remain in their original workspace folders.
    files = [ROOT/name for name in ['AGENTS.md', 'README.md', 'research/OSC质感诊断V1.html',
        'research/OSC质感诊断V1.md', 'research/goal_progress_osc_quality_v1.json',
        'research/quality_direction_20261110.json', 'research/听评记录.md',
        'tools/diagnose_osc_quality_v1.py', 'tools/refine_osc_quality_v1.py',
        'tools/export_quality_candidate_v1.py', 'tools/audit_osc_quality_v1.py',
        'tools/verify_osc_quality_v1.cjs', 'tools/seekable_review_player_v1.js',
        'tools/runtime_review.py', 'tools/reference_segments.py', 'tools/sinusoidal_experiment.py']]
    files += [p for p in (ROOT/'tools/osc_quality_v1').glob('*.py')]
    files += [p for p in (ROOT/'tools/reference_osc_v1').glob('*.py')]
    files += [p for p in (ROOT/'experiments/reference_osc_v1').iterdir() if p.is_file()]
    files += [p for p in OUT.rglob('*') if p.is_file() and '4x' not in p.name
              and 'unused_high' not in p.name and p.name != 'progress.json']
    files += [probe, ROOT/'references/analysis/reference_osc_v1/archive64.model']
    assert len(files) == len(set(files))
    SNAPSHOT.mkdir()
    entries = []
    for source in sorted(files):
        relative = source.relative_to(ROOT)
        dest = SNAPSHOT/relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
        expected = sha(source)
        assert sha(dest) == expected
        entries.append(dict(path=relative.as_posix(), sha256=expected))
    manifest = dict(version='osc_quality_v1', native_application='0.20.0 unchanged',
        status='Technical controls passed; subjective quality pending; high tuning deferred.',
        scope='Six-second pure-OSC coefficient reconstruction, not sustained arbitrary RPM/load synthesis.',
        previous_snapshot_manifests=snapshots, files=entries)
    (SNAPSHOT/'manifest.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(dict(result='pass', previous_snapshots=len(snapshots), previous_files=checked_files,
        native_unchanged=len(native), new_snapshot_files=len(entries), report_links=statuses), ensure_ascii=False))


if __name__ == '__main__':
    main()

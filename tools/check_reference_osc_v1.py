"""Check transfer evidence, historical preservation and unchanged native release."""
from runtime_review import ROOT, sha
import json
import subprocess

OUT = ROOT/'references/analysis/reference_osc_v1'


def main():
    report = json.loads((OUT/'results.json').read_text(encoding='utf-8'))
    probe = ROOT/'build-reference-osc-v1/Release/reference_osc_probe.exe'
    assert sha(probe) == report['probe_sha256']
    assert report['archive']['max_original_pcm24_error'] <= 2/8388608
    for name, digest in report['preserved_before'].items():
        assert digest == report['preserved_after'][name] == sha(ROOT/name), name
    browser = json.loads((OUT/'browser_qa.json').read_text())
    assert browser['loads'] == 13 and not browser['errors']
    for value in report['excerpts'].values():
        assert value['max_c_float_error'] < 1e-7
        for item in value['audition']['files'].values():
            assert sha(OUT/item['file']) == item['sha256']
    native = json.loads((ROOT/'baselines/v0.20.0/manifest.json').read_text(encoding='utf-8'))
    native_checked = 0
    for item in native['files']:
        if item['path'].startswith(('src/', 'tests/')):
            assert sha(ROOT/item['path']) == item['sha256'], item['path']
            native_checked += 1
    snapshots, count = {}, 0
    for path in sorted((ROOT/'baselines').glob('*/manifest.json')):
        manifest = json.loads(path.read_text(encoding='utf-8'))
        snapshots[path.parent.name] = sha(path)
        for item in manifest['files']:
            assert sha(path.parent/item['path']) == item['sha256'], (path.parent.name, item['path'])
            count += 1
    tests = subprocess.run(['ctest', '--test-dir', 'build-reference-osc-v1', '-C',
        'Release', '--output-on-failure'], cwd=ROOT, check=True, capture_output=True, text=True)
    sources = [*sorted((ROOT/'experiments/reference_osc_v1').glob('*')),
        *sorted((ROOT/'tools/reference_osc_v1').glob('*.py')),
        ROOT/'tools/recover_reference_osc_v1.py', ROOT/'tools/verify_reference_osc_v1.cjs',
        ROOT/'tools/check_reference_osc_v1.py', ROOT/'research/素材OSC回查V1.html',
        ROOT/'research/素材驱动OSC回查V1.md']
    value = dict(result='pass', probe_sha256=sha(probe),
        ctest_output=tests.stdout, browser=browser,
        preserved_snapshot_manifests=snapshots, preserved_snapshot_files=count,
        unchanged_native_source_and_test_files=native_checked,
        source_hashes={str(p.relative_to(ROOT)):sha(p) for p in sources if p.is_file()},
        artifacts={p.name:sha(p) for p in sorted(OUT.iterdir()) if p.is_file() and p.name!='verification.json'},
        subjective_acceptance=False,
        limits='Independent excerpt reconstruction diagnostic, not integrated native DSP, arbitrary RPM/load generalization or a naturalness claim.')
    (OUT/'verification.json').write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f'PASS: {len(snapshots)} snapshots / {count} files, {native_checked} native source/tests unchanged; C contracts and 13 browser clips passed.')


if __name__ == '__main__':
    main()

"""Verify accepted-base identity, pitch/HF contracts and actual preview evidence."""
from runtime_review import ROOT, sha
import json
import subprocess
import numpy as np
import soundfile as sf

OUT = ROOT/'references/analysis/reference_osc_v2'


def main():
    r = json.loads((OUT/'results.json').read_text(encoding='utf-8'))
    assert sha(ROOT/r['accepted_baseline']['accepted_reference']['file']) == r['accepted_baseline']['accepted_reference']['sha256']
    assert sha(ROOT/'build-reference-osc-v2/Release/tracked_osc_probe.exe') == r['probe_sha256']
    base, rate = sf.read(OUT/'base_float.wav', dtype='float32', always_2d=True)
    old, old_rate = sf.read(ROOT/'references/analysis/reference_osc_v1/archive64_c_float.wav', dtype='float32', always_2d=True)
    assert rate == old_rate == 48000 and np.array_equal(base, old)
    first, stop = r['high_active_samples']
    high = []
    for name in ['high25', 'high50', 'pitch90', 'pitch110']:
        value, sr = sf.read(OUT/f'{name}_float.wav', dtype='float32', always_2d=True)
        assert sr == rate and value.shape == base.shape and np.isfinite(value).all()
        if name.startswith('high'):
            assert np.array_equal(value[:first], base[:first]) and np.array_equal(value[stop:], base[stop:])
            high.append(value.astype(float)-base)
    assert abs(high[1]-2*high[0]).max() < 1e-7
    for item in r['auditions'].values():
        assert sha(OUT/item['file']) == item['sha256'] and item['peak'] < .95
    browser = json.loads((OUT/'browser_qa.json').read_text())
    native = json.loads((OUT/'native_preview.json').read_text())
    assert browser['loads'] == 6 and not browser['errors']
    assert native['result'] == 'pass' and native['device_muted'] and native['frames'] == len(base)
    assert native['queue_empty'] == 0 and .95 < native['device_seconds']/native['wall_seconds'] < 1.03
    assert native['ui_controls'] and native['live_max_pitch'] > 1.09 and native['live_max_high'] > .49
    h = 14695981039346656037
    for byte in base.astype('<f4').tobytes():
        h = ((h ^ byte)*1099511628211)&((1 << 64)-1)
    assert format(h, '016x') == native['raw_float_hash']
    snapshots, count = {}, 0
    for path in sorted((ROOT/'baselines').glob('*/manifest.json')):
        snapshots[path.parent.name] = sha(path)
        for item in json.loads(path.read_text(encoding='utf-8'))['files']:
            assert sha(path.parent/item['path']) == item['sha256'], (path.parent.name, item['path'])
            count += 1
    unchanged = 0
    for item in json.loads((ROOT/'baselines/v0.20.0/manifest.json').read_text(encoding='utf-8'))['files']:
        if item['path'].startswith(('src/', 'tests/')):
            assert sha(ROOT/item['path']) == item['sha256'], item['path']
            unchanged += 1
    tests = subprocess.run(['ctest', '--test-dir', 'build-reference-osc-v2', '-C', 'Release', '--output-on-failure'],
        cwd=ROOT, check=True, capture_output=True, text=True)
    paths = [*sorted((ROOT/'experiments/reference_osc_v2').glob('*')),
        *sorted((ROOT/'tools/reference_osc_v2').glob('*.py')),
        ROOT/'tools/review_reference_osc_v2.py', ROOT/'tools/verify_reference_osc_v2.cjs',
        ROOT/'tools/check_reference_osc_v2.py', ROOT/'tools/freeze_reference_osc_v2.py',
        ROOT/'research/旧64OSC高频V2.html', ROOT/'research/旧64OSC高频V2.md',
        ROOT/'research/timbre_baseline_20261110.json', ROOT/'research/goal_progress_reference_osc_v2.json', ROOT/'Launch-reference64.cmd']
    paths += [ROOT/'experiments/reference_osc_v1'/name for name in ['model.h', 'model.c', 'oscillator.h', 'oscillator.c']]
    paths += [ROOT/'baselines/v0.20.0/src/io'/name for name in ['wav.h', 'wav.c', 'file.h', 'file.c']]
    paths += [ROOT/'tools'/name for name in ['sinusoidal_experiment.py', 'osc_research/tracker.py', 'reference_segments.py',
        'runtime_review.py', 'reference_osc_v1/exporter.py', 'reference_osc_v1/observations.py']]
    result = dict(result='pass', accepted_base='original64OSC only', added_high_and_pitch_accepted=False,
        native_DSP020_changed=False, unchanged_native_source_tests=unchanged,
        raw_float_hash=native['raw_float_hash'], baseline_unit_pitch_exact=True, high_linearity=True,
        exterior_only_high=True, ctest_output=tests.stdout, native=native, browser=browser,
        old_snapshot_manifests=snapshots, old_snapshot_files=count,
        binaries={p.name:sha(p) for p in sorted((ROOT/'build-reference-osc-v2/Release').glob('*.exe'))},
        source_hashes={str(p.relative_to(ROOT)):sha(p) for p in paths if p.is_file()},
        artifacts={str(p.relative_to(OUT)):sha(p) for p in sorted(OUT.rglob('*')) if p.is_file() and p.name != 'verification.json'},
        limit='Six-second fitted parameter voice. Not sustained RPM/load engine calibration, native driving integration or a naturalness score.')
    (OUT/'verification.json').write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f'PASS: exact accepted base, exterior-only HF, native rawfloat/device/UI, six browser clips; {len(snapshots)} snapshots/{count} files and{unchanged} native source/tests preserved.')


if __name__ == '__main__':
    main()

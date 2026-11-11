"""Verify native main-pressure shape, exact bypass and fresh-take reconstruction."""
import csv
import json
import shutil
import subprocess
from runtime_review import ROOT, sha, rms
from review_audit import device
from render_event_color import CASES
import numpy as np
import soundfile as sf
from PIL import Image

OUT = ROOT/'renders/v0.19.0'
BUILD = ROOT/'build-v019/Release'
NEW_COLUMNS = {'event_color_target', 'event_color_mix', 'event_color_events_l',
               'event_color_events_r', 'event_color_max_mod'}


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def run(args):
    return subprocess.run(list(map(str, args)), cwd=ROOT, check=True,
                          capture_output=True, text=True, timeout=120).stdout


def rows(path):
    with path.open(encoding='utf-8') as f:
        return list(csv.DictReader(f))


def audio(path):
    x, sr = sf.read(path, always_2d=True)
    assert sr == 48000 and sf.info(path).subtype == 'FLOAT'
    assert np.isfinite(x).all() and abs(x).max() < .95
    return x


def create():
    if (OUT/'verification.json').exists() or (ROOT/'baselines/v0.19.0').exists():
        raise SystemExit('Preserve completed V019.')
    native = read(OUT/'ui_smoke.json')
    device(native, '0.19.0')
    for key in ['character_controls', 'character_preset_roundtrip', 'character_legacy_preset',
                'character_active_on_device', 'propagation_control', 'propagation_preset_roundtrip',
                'propagation_active_on_device', 'response_control', 'response_preset_roundtrip',
                'response_legacy_preset', 'response_active_on_device', 'event_color_control',
                'event_color_preset_roundtrip', 'event_color_legacy_preset', 'event_color_active_on_device']:
        assert native[key], key
    take_report = read(OUT/'ui_take_smoke.json')
    take = take_report['result']
    for key in ['character_state_match', 'device_character_state_match',
                'response_state_match', 'device_response_state_match',
                'event_color_state_match', 'device_event_color_state_match']:
        assert take_report[key] == 1, key
    for key in ['saved', 'loaded', 'offline_hash_match', 'final_drive_state_match',
                'device_replay_hash_and_state_match', 'manual_replay_stop', 'controls_locked', 'muted']:
        assert take[key] == 1, key
    assert take['replay_queue_empty'] == 0
    assert .95 < take['replay_device_seconds']/take['replay_wall_seconds'] < 1.02
    assert all(read(OUT/'ui_take_controls.json').values())
    for path in OUT.glob('*.bmp'):
        with Image.open(path) as image:
            image.save(path.with_suffix('.png'))
    log = ROOT/'build-v019/Testing/Temporary/LastTest.log'
    assert log.read_bytes().count(b'Test Passed.') == 21
    assert b'live_main_pressure_color' in log.read_bytes()
    shutil.copy2(log, OUT/'ctest.log')
    default = {}
    for profile in range(5):
        paths = []
        for tag in ['v018', 'v019']:
            path = OUT/f'{tag}_default_profile_{profile}.wav'
            run([ROOT/f'build-{tag}/Release/vsl_render.exe', path, '--profile', profile,
                 '--rpm', 4000, '--load', .65, '--seconds', 3])
            paths.append(path)
        assert paths[0].read_bytes() == paths[1].read_bytes(), profile
        default[str(profile)] = sha(paths[1])
    folder = OUT/'comparisons'
    folder.mkdir(exist_ok=True)
    comparisons = {}
    for name, (label, scenario, seconds, rpm, load, pressure, structure, shape) in CASES.items():
        signals = {}
        traces = {}
        for tag, build, amount in [('v018', 'v018', None), ('off', 'v019', 0), ('on', 'v019', 1)]:
            prefix = folder/f'{name}_{tag}'
            args = [ROOT/f'build-{build}/Release/vsl_character_probe.exe', prefix.with_suffix('.vsltake'),
                    scenario, seconds, rpm, load, pressure, structure, shape]
            if amount is not None:
                args.append(amount)
            run(args)
            run([ROOT/f'build-{build}/Release/vsl_take_render.exe', prefix.with_suffix('.vsltake'),
                 prefix.with_suffix('.wav')])
            signals[tag] = audio(prefix.with_suffix('.wav'))
            traces[tag] = rows(folder/f'{name}_{tag}.vsltake.csv')
        assert (folder/f'{name}_v018.wav').read_bytes() == (folder/f'{name}_off.wav').read_bytes(), name
        columns = set(traces['v018'][0])
        assert set(traces['off'][0])-columns == NEW_COLUMNS
        for tag in ['off', 'on']:
            assert len(traces[tag]) == len(traces['v018'])
            assert all(all(a[k] == b[k] for k in columns)
                       for a, b in zip(traces['v018'], traces[tag])), (name, tag)
        assert all(all(a[k] == b[k] for k in ['event_color_events_l', 'event_color_events_r'])
                   for a, b in zip(traces['off'], traces['on']))
        # A frozen STATIC prototype starts with amount1; native uses an18ms
        # parameter follower. Compare only after2.5s, beyond initial response tails.
        frozen = audio(ROOT/f'renders/event_color_v1/{name}/full.wav')
        assert frozen.shape == signals['on'].shape
        error = float(abs(frozen[120000:]-signals['on'][120000:]).max())
        assert error <= 1.2e-7, (name, error)
        delta = signals['on']-signals['off']
        assert abs(delta).max() > 0, name
        comparisons[name] = dict(main_shape_zero_exact_V018_float_and_WAV=True,
            original_trace_columns_identical=sorted(columns), original_and_color_event_counts_unchanged=True,
            static_prototype_comparison_start_seconds=2.5, static_prototype_max_float_error=error,
            complete_mix_difference_to_original_db=rms(delta)-rms(signals['off']),
            change_in_RMS_db=rms(signals['on'])-rms(signals['off']))
        print(json.dumps(dict(case=name, prototype_float_error=error,
            difference_to_original_db=comparisons[name]['complete_mix_difference_to_original_db']), allow_nan=False), flush=True)
    stem_folder = OUT/'stems'
    stem_folder.mkdir(exist_ok=True)
    take_path = OUT/'ui_take_smoke.vsltake'
    for channels in [2, 12]:
        run([BUILD/'vsl_take_render.exe', take_path, OUT/f'take_{channels}.wav', '--channels', channels,
             '--trace', OUT/f'take_{channels}.csv', '--stems', stem_folder/f'take_{channels}'])
    assert (OUT/'take_2.wav').read_bytes() == (OUT/'ui_take_smoke.wav').read_bytes()
    assert (OUT/'take_2.csv').read_bytes() == (OUT/'take_12.csv').read_bytes()
    stems = list(stem_folder.glob('take_2_*.wav'))
    assert len(stems) == 10
    for path in stems:
        assert path.read_bytes() == path.with_name(path.name.replace('take_2_', 'take_12_')).read_bytes()
    for exe, path in [(BUILD/'vsl_take_render.exe', ROOT/'renders/v0.18.0/ui_take_smoke.vsltake'),
                      (ROOT/'build-v018/Release/vsl_take_render.exe', take_path)]:
        target = OUT/'incompatible.wav'
        p = subprocess.run([str(exe), str(path), str(target)], cwd=ROOT, capture_output=True)
        assert p.returncode == 2 and not target.exists()
    preserved, changed = {}, {}
    old_manifest = read(ROOT/'baselines/v0.18.0/manifest.json')
    for item in old_manifest['files']:
        name = item['path']
        if name.startswith(('src/', 'tests/')) or name == 'CMakeLists.txt':
            digest = sha(ROOT/name)
            if digest == item['sha256']:
                preserved[name] = digest
            else:
                changed[name] = dict(v018=item['sha256'], v019=digest)
    expected = {'CMakeLists.txt', 'src/core/types.h', 'src/core/engine.c', 'src/core/profiles.c',
                'src/core/character.c', 'src/session/parameters.h', 'src/io/take_file.c',
                'src/io/scene_metadata.c', 'src/io/drive_trace.c', 'src/app/preset.c', 'src/app/tuning.c',
                'src/app/audio_device.c', 'src/app/audio_device.h', 'src/app/main.c',
                'src/app/take_smoke.c', 'tests/test_take.c'}
    assert set(changed) == expected, set(changed)^expected
    historical = {}
    for version, tag in [('0.15.0', 'v015'), ('0.16.0', 'v016'), ('0.17.0', 'v017'), ('0.18.0', 'v018')]:
        binaries = read(ROOT/f'renders/v{version}/verification.json')['binaries']
        for name, digest in binaries.items():
            assert sha(ROOT/f'build-{tag}/Release'/name) == digest, (version, name)
        historical[version] = binaries
    for name in ['src/core/dna.c', 'src/core/high_orders.c', 'src/core/exhaust_spectrum.c', 'src/profiles/high_orders.c']:
        assert sha(ROOT/name) == sha(ROOT/'baselines/v0.11.0'/name)
    history = {p.parent.name: sha(p) for p in sorted((ROOT/'baselines').glob('*/manifest.json'))}
    assert len(history) == 34
    result = dict(result='pass', version='0.19.0', seed=48271, ctest_count=21,
        device=native, take=take_report, unchanged_default_templates=default, comparisons=comparisons,
        stereo_714_identical_source_stems=10, complete_layout_traces_identical=True,
        strict_V018_V019_take_boundary=True, V018_contract_files_unchanged=preserved,
        V018_contract_files_intentionally_changed=changed, previous_native_binaries_unchanged=historical,
        previous_snapshot_manifest_identities=history,
        binaries={p.name: sha(p) for p in sorted(BUILD.iterdir()) if p.suffix in ['.exe', '.lib']},
        subjective_status='Optional main-pressure control, default0. No subjective acceptance, physical pressure calibration or realism score inferred.')
    result['files'] = {p.relative_to(OUT).as_posix(): sha(p) for p in sorted(OUT.rglob('*')) if p.is_file()}
    (OUT/'verification.json').write_text(json.dumps(result, indent=2, allow_nan=False), encoding='utf-8')
    print('V019 native device, defaults, seven fresh-take comparisons and layouts pass.', flush=True)


def audit():
    result = read(OUT/'verification.json')
    assert result['result'] == 'pass' and result['version'] == '0.19.0'
    for name, digest in result['files'].items():
        assert sha(OUT/name) == digest, name
    for name, digest in result['binaries'].items():
        assert sha(BUILD/name) == digest, name
    sources = [ROOT/'CMakeLists.txt', *(ROOT/'src').rglob('*.c'), *(ROOT/'src').rglob('*.h'),
               *(ROOT/'tests').glob('*.c')]
    names = ['README.md', 'AGENTS.md', '.gitignore', 'Launch.cmd', 'Launch-character.cmd',
             'Launch-v017.cmd', 'Launch-v018.cmd', 'Launch-response-shape.cmd', 'Launch-main-pressure.cmd', 'Launch-current.cmd', 'build.ps1',
             'research/V019实时主排气形状.md', 'research/goal_progress_v019.json',
             'research/主排气逐次形状实验V1.md', 'research/upstream_v6_response/v10_powertrain.gendsp',
             'tools/verify_v019.py', 'tools/freeze_v019.py', 'tools/freeze_review.py',
             'tools/runtime_review.py', 'tools/review_audit.py', 'tools/v016_probe.c',
             'tools/integrate_event_color_v019.py', 'tools/render_event_color.py', 'tools/reference_segments.py',
             'baselines/event_color_v1/manifest.json']
    report = dict(result='pass', version='0.19.0', ctest_count=21,
        source_code={p.relative_to(ROOT).as_posix(): sha(p) for p in sorted(sources)},
        deliverables={name: sha(ROOT/name) for name in names},
        rendered_artifacts={p.relative_to(OUT).as_posix(): sha(p) for p in sorted(OUT.rglob('*'))
                            if p.is_file() and p.name != 'workspace_audit.json'},
        goal_status='active; optional native main-pressure control ready, timbre and array listening unresolved')
    (OUT/'workspace_audit.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('V019 source and artifact audit passed. Broad goal remains active.')


if __name__ == '__main__':
    import sys
    audit() if '--audit' in sys.argv else create()

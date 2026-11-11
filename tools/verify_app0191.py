"""Verify app-only keyboard repair, native self-tests and DSP019 take parity."""
import json
import shutil
import subprocess
from runtime_review import ROOT, sha
from review_audit import device
from PIL import Image

OUT = ROOT/'renders/app0.19.1'
BUILD = ROOT/'build-app0191/Release'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def main():
    if (OUT/'verification.json').exists() or (ROOT/'baselines/app0.19.1').exists():
        raise SystemExit('Preserve completed app0.19.1 verification.')
    keys = read(OUT/'ui_input.json')
    assert keys['app'] == '0.19.1' and keys['dsp'] == '0.19.0' and not keys['system_input_injection']
    names = ['SCI_FI_type_search', 'selection_does_not_brake', 'mode_selection_does_not_shift',
        'brake_shortcut', 'brake_release_after_focus_change', 'throttle_shortcut',
        'throttle_release_after_focus_change', 'focus_loss_releases_pedals']
    assert all(keys[name] == 1 for name in names)
    native = read(OUT/'ui_smoke.json')
    device(native, '0.19.0')
    assert all(value for value in native.values() if isinstance(value, bool))
    take = read(OUT/'ui_take_smoke.json')
    assert all(v == 1 for k, v in take.items() if k != 'result')
    for name in ['saved', 'loaded', 'offline_hash_match', 'final_drive_state_match',
                 'device_replay_hash_and_state_match', 'manual_replay_stop', 'controls_locked', 'muted']:
        assert take['result'][name] == 1, name
    assert take['result']['dsp'] == '0.19.0' and take['result']['replay_queue_empty'] == 0
    assert .95 < take['result']['replay_device_seconds']/take['result']['replay_wall_seconds'] < 1.02
    assert all(read(OUT/'ui_take_controls.json').values())
    log = ROOT/'build-app0191/Testing/Temporary/LastTest.log'
    assert log.read_bytes().count(b'Test Passed.') == 22
    assert b'native_driver_key_routing' in log.read_bytes()
    shutil.copy2(log, OUT/'ctest.log')
    for path in OUT.glob('*.bmp'):
        with Image.open(path) as image:
            image.save(path.with_suffix('.png'))
    baseline = read(ROOT/'baselines/v0.19.0/manifest.json')
    changed, preserved = {}, {}
    old_names = set()
    for item in baseline['files']:
        name = item['path']
        if name.startswith(('src/', 'tests/')) or name == 'CMakeLists.txt':
            old_names.add(name)
            digest = sha(ROOT/name)
            if digest == item['sha256']:
                preserved[name] = digest
            else:
                changed[name] = dict(old=item['sha256'], new=digest)
    assert set(changed) == {'CMakeLists.txt', 'src/app/main.c', 'src/app/take_smoke.c'}
    new_sources = {p.relative_to(ROOT).as_posix():sha(p) for folder in ['src', 'tests']
        for p in (ROOT/folder).rglob('*') if p.suffix in ['.c', '.h'] and p.relative_to(ROOT).as_posix() not in old_names}
    assert set(new_sources) == {'src/app/driver_keys.c', 'src/app/driver_keys.h', 'src/app/ui_input_check.c',
        'src/app/ui_input_check.h', 'src/app/version.h', 'tests/test_driver_keys.c'}
    old_binaries = read(ROOT/'renders/v0.19.0/verification.json')['binaries']
    for name, digest in old_binaries.items():
        assert sha(ROOT/'build-v019/Release'/name) == digest, name
    legacy = ROOT/'experiments/ui_display_v1/legacy_sandbox'
    assert sha(legacy/'VehicleSoundLab.exe') == old_binaries['VehicleSoundLab.exe']
    assert all(v for v in read(legacy/'renders/v0.19.0/ui_smoke.json').values() if isinstance(v, bool))
    take_checks = {}
    for name, path in [('old019', ROOT/'renders/v0.19.0/ui_take_smoke.vsltake'),
                       ('app0191', OUT/'ui_take_smoke.vsltake')]:
        wavs, traces = [], []
        for tag, exe in [('old', ROOT/'build-v019/Release/vsl_take_render.exe'),
                         ('new', BUILD/'vsl_take_render.exe')]:
            wav = OUT/f'compat_{name}_{tag}.wav'
            trace = OUT/f'compat_{name}_{tag}.csv'
            subprocess.run([str(exe), str(path), str(wav), '--trace', str(trace)],
                           cwd=ROOT, capture_output=True, check=True, timeout=45)
            wavs.append(wav);traces.append(trace)
        assert wavs[0].read_bytes() == wavs[1].read_bytes(), name
        assert traces[0].read_bytes() == traces[1].read_bytes(), name
        take_checks[name] = dict(take_sha256=sha(path), identical_float_WAV_sha256=sha(wavs[0]),
                                identical_complete_trace_sha256=sha(traces[0]))
        print('DSP019 take compatibility:', name, 'exact WAV and trace.', flush=True)
    history = {p.parent.name:sha(p) for p in sorted((ROOT/'baselines').glob('*/manifest.json'))}
    assert len(history) == 36
    result = dict(result='pass', app='0.19.1', dsp='0.19.0', ctest_count=22,
        native_input_message_loop=keys, muted_device=native, take=take,
        DSP019_take_compatibility=take_checks, previous_binaries=old_binaries,
        original_source_files_preserved=preserved, intentional_app_only_changes=changed,
        new_sources=new_sources, previous_snapshot_manifest_identities=history,
        legacy_visible_self_test='Original frozen019 binary in isolated sandbox, no system input injection. Selected labels were visible; historical hidden WM_PRINT capture omitted them.',
        legacy_sandbox_files={p.relative_to(legacy).as_posix():sha(p) for p in sorted(legacy.rglob('*')) if p.is_file()},
        binaries={p.name:sha(p) for p in sorted(BUILD.iterdir()) if p.suffix in ['.exe', '.lib']},
        limitations='Application message routing repair. No voicing, source, drive, spatial or take-schema change. No external SendInput/physical-keyboard or physical speaker-array listening claim; subjective candidates remain pending.')
    result['files'] = {p.relative_to(OUT).as_posix():sha(p) for p in sorted(OUT.rglob('*')) if p.is_file()}
    (OUT/'verification.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print('App0191 native input, muted device and unchanged DSP019 verified.')


if __name__ == '__main__':
    main()

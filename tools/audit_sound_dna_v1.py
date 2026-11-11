"""Check recorded evidence and preserve the generic DNA foundation separately."""
from runtime_review import ROOT, sha
import json
import shutil
import tempfile
from pathlib import Path


OUT = ROOT / 'references/analysis/sound_dna_v1'
NATIVE = ROOT / 'references/analysis/sustain_monitor_v3'
SNAPSHOT = ROOT / 'baselines/sound_dna_v1'


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def check_hashes(items, base=ROOT):
    for path, identity in items.items():
        assert sha(base / path) == identity, path


def main():
    if SNAPSHOT.exists():
        raise SystemExit('Preserve sound_dna_v1; use a new version.')

    # Inherit the immutable manifest identities, rather than trusting new hashes
    # as proof that historical snapshots have stayed unchanged.
    previous = ROOT / 'baselines/detail_low_v1'
    expected = read(previous / 'references/analysis/sustain_monitor_v2/audit.json')['old_snapshot_manifests']
    expected['detail_low_v1'] = sha(previous / 'manifest.json')
    snapshots = {}
    total = 0
    for manifest in sorted((ROOT / 'baselines').glob('*/manifest.json')):
        assert sha(manifest) == expected[manifest.parent.name], manifest
        entries = read(manifest)['files']
        check_hashes({item['path']: item['sha256'] for item in entries}, manifest.parent)
        snapshots[manifest.parent.name] = sha(manifest)
        total += len(entries)
    assert set(snapshots) == set(expected) and len(snapshots) == 46 and total == 6065

    driving = [item for item in read(ROOT / 'baselines/v0.20.0/manifest.json')['files']
               if item['path'].replace('\\', '/').startswith(('src/', 'tests/'))]
    check_hashes({item['path']: item['sha256'] for item in driving})
    assert len(driving) == 170
    for rel, build in [('detail_osc_v1', 'build-detail-osc-v1'),
                       ('sustain_monitor_v1', 'build-sustain-monitor-v1'),
                       ('sustain_monitor_v2', 'build-sustain-monitor-v2')]:
        proof = read(ROOT / 'references/analysis' / rel / 'verification.json')
        check_hashes(proof['source_hashes'])
        check_hashes(proof['binaries'], ROOT / build / 'Release')

    offline = read(OUT / 'verification.json')
    native = read(NATIVE / 'verification.json')
    legacy = read(OUT / 'legacy_interchange/dna_pipeline_check.json')
    assert offline['result'] == native['result'] == legacy['result'] == 'pass'
    # The offline render preceded a later dropdown-refresh/screenshot repair.
    # Check its algorithm/render inputs, and the final native proof for all UI.
    superseded_ui = {'bank.c', 'smoke.c', 'ui.c'}
    offline_current = {path: identity for path, identity in offline['source_hashes'].items()
                       if path.replace('\\', '/').rsplit('/', 1)[-1] not in superseded_ui}
    check_hashes(offline_current)
    check_hashes(native['source_hashes'])
    check_hashes(native['binaries'], ROOT / 'build-sustain-monitor-v3/Release')
    check_hashes(native['evidence'])
    assert offline['accepted_phase_fixed_max_float_error'] == 0
    assert offline['unicode_profile_and_export'] and offline['zero_component_static_note']
    assert offline['unsafe_truncated_nan_trailing_models_rejected']
    assert native['accepted_fixed_phase_recipe_preserved']
    assert native['bank_checks'] == dict(result=True, voice_count=3, failed_load_preserves_profile=True)
    assert native['max_device_pre_envelope_error'] < 2e-8
    for section in ['baseline', 'live']:
        run = native['native'][section]
        assert run['queue_empty'] == 0 and not run['error'] and run['frames'] == 384000
        assert .95 < run['device_seconds'] / run['playback_wall_seconds'] < 1.02
        assert run['render_ms_mean'] < 512 / 48
    assert sha(ROOT / 'build-v020/Release/vsl_render.exe') == legacy['renderer_sha256']

    accepted = read(ROOT / 'research/sound_dna_acceptance_20261110.json')
    assert sha(ROOT / accepted['reference']) == accepted['reference_sha256']
    assert accepted['new_default_float_matches_reference'] and not accepted['goal_complete']
    bank = read(ROOT / 'voices/dna_bank_v1/index.json')
    assert len(bank['voices']) == 3
    for item in bank['voices']:
        name = item['name']
        voice = offline['voices'][name]
        assert sha(ROOT / 'voices/dna_bank_v1' / item['file']) == item['model_sha256'] == voice['model_sha256']
        assert sha(OUT / 'renders' / f'{name}_raw_float.wav') == voice['raw_sha256']
        assert sha(OUT / 'renders' / f'{name}_audition.wav') == voice['audition_sha256']
        assert voice['bounded_pitch_preserves_duration']
        if 'build' in item:
            build = read(ROOT / item['build'])
            assert sha(build['source']) == build['source_sha256']
            assert sha((ROOT / item['build']).parent / 'voice.model') == build['model_sha256'] == item['model_sha256']
    assert sha(ROOT / 'voices/dna_bank_v1/V10 Exterior.model') == sha(ROOT / 'references/analysis/sustain_osc_v1/voice.model') == native['profile_sha256']

    folders = ['modules/sound_dna', 'experiments/sustain_monitor_v3',
               'tools/sound_dna', 'voices/dna_bank_v1',
               'references/analysis/sound_dna_v1', 'references/analysis/sustain_monitor_v3']
    audit = dict(result='pass', old_snapshot_manifests=snapshots, old_snapshot_files=total,
                 native_source_tests_unchanged=len(driving), previous_previews_unchanged=True,
                 fixed_phase_reference_max_float_error=0,
                 same_generator_model_count=3, real_engine_model_count=1,
                 final_native_source_hash=native['unmodified_source_float_hash'],
                 final_native_pre_envelope_error=native['max_device_pre_envelope_error'],
                 legacy_interchange='pass', low_layer='Unaccepted and paused by user',
                 subjective_scope=accepted['scope'], new_native_listening_acceptance=False,
                 offline_ui_hashes_superseded_by_final_native=sorted(superseded_ui),
                 desktop_visual_qa='Hidden-window combo text not reliable; live desktop screenshot unavailable',
                 goal_complete=False,
                 limits='One accepted V10 context plus two analytic fixtures demonstrate reuse; not multiple real-car or arbitrary synth-patch realism.')
    (OUT / 'audit.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding='utf-8')

    files = [p for folder in folders for p in (ROOT / folder).rglob('*')
             if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc']
    files += [ROOT / path for path in [
        'AGENTS.md', 'README.md', 'Launch-sound-dna.cmd',
        'research/soundDNA通用结构V1.md', 'research/sound_dna_acceptance_20261110.json',
        'research/goal_progress_sound_dna_v1.json', 'research/sustain_acceptance_20261110.json',
        'research/goal_progress_detail_low_v1.json', 'research/听评记录.md',
        'tools/compile_sound_dna.py', 'tools/prepare_dna_bank_v1.py',
        'tools/verify_sound_dna_v1.py', 'tools/verify_sustain_monitor_v3.py',
        'tools/audit_sound_dna_v1.py', 'tools/runtime_review.py',
        'baselines/v0.20.0/src/io/wav.h', 'baselines/v0.20.0/bin/vsl_core.lib']]
    files += [ROOT / 'build-sustain-monitor-v3/Release' / name for name in native['binaries']]
    files += [ROOT / 'build-sustain-monitor-v3/sound-dna-core/Release/sound_dna.lib']
    assert len(files) == len(set(files)) and all(p.is_file() for p in files)
    # Stage a new snapshot, then rename; never overwrite an earlier version.
    staging = Path(tempfile.mkdtemp(prefix='.sound-dna-v1-', dir=ROOT / 'baselines'))
    entries = []
    for source in sorted(files):
        rel = source.relative_to(ROOT)
        dest = staging / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
        identity = sha(source)
        assert sha(dest) == identity, rel
        entries.append(dict(path=rel.as_posix(), sha256=identity))
    manifest = dict(version='sound_dna_v1',
                    scope='Independent fixed-phase statistical OSC DNA library, explicit-root compiler and native voice monitor.',
                    subjective_status='Fixed-phase V10 diagnostic accepted; new GUI and other real-engine voices not separately accepted.',
                    main_driving_DSP='0.20.0 unchanged',
                    old_snapshot_manifests=snapshots, files=entries)
    (staging / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    staging.rename(SNAPSHOT)
    print(json.dumps(dict(result='pass', old_snapshots=len(snapshots), old_files=total,
                          new_snapshot_files=len(entries), native_source_tests_unchanged=len(driving))))


if __name__ == '__main__':
    main()

"""Publish/freeze fixed E low-state observations; never fit or change runtime."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace', type=Path, required=True)
parser.add_argument('--stage', choices=['publish', 'freeze'], required=True)
args = parser.parse_args()
repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(args.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from drive_evidence_v1.sources import sha

base = args.workspace/'references/analysis/E_low_state_v1'
summary_path = repo/'research/E_low_state_v1_summary.json'
final = base/'final1'


def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


if args.stage == 'publish':
    final.mkdir(exist_ok=False)
    result = dict(schema='vsl.E-low-state-publication/1', result='running', reports={}, sources={})
    try:
        reports = {name: base/name/'report.json' for name in
                   ('inspect1', 'observe1', 'observe2', 'qualify1', 'track_audit1')}
        reports['prelaunch_inspect1'] = args.workspace/'references/analysis/E_prelaunch_v1/inspect1/report.json'
        data = {name: load(path) for name, path in reports.items()}
        assert data['observe1']['result'] == 'failed'
        assert data['observe2']['result'] == 'observed_not_fitted'
        assert data['qualify1']['result'] == 'local_diagnostics_only'
        assert data['track_audit1']['result'] == 'audited_without_retry'
        assert not data['qualify1']['cases']['exterior_before_blips']['local_diagnostic_gate']
        assert not any(base.rglob('*.model'))
        for name, path in reports.items():
            result['reports'][name] = dict(path=path.relative_to(args.workspace).as_posix(), sha256=sha(path))
            if name not in ('inspect1', 'prelaunch_inspect1', 'observe1'):
                for relative, digest in data[name]['sources'].items():
                    assert sha(path.parent/'exact_sources'/relative) == digest
                    assert sha(repo/relative) == digest
        frames = 0
        for name in ('inspect1', 'prelaunch_inspect1'):
            source = data[name]['sources']['E']
            assert sha(Path(source['video'])) == source['video_sha256']
            directory = reports[name].parent/'E'
            for item in source['frames']+source['boards']:
                assert sha(directory/item['file']) == item['sha256']
            frames += len(source['frames'])
        assert frames == 42
        observed = data['observe2']
        master = args.workspace/observed['input']['master']
        assert sha(master) == observed['input']['master_sha256']
        for name, item in observed['segments'].items():
            path = base/'observe2'/name/'unchanged_reference.wav'
            assert sha(path) == item['unchanged_reference_sha256']
            clip, rate = sf.read(path, dtype='float64', always_2d=True)
            with sf.SoundFile(master) as stream:
                stream.seek(item['first_sample'])
                original = stream.read(item['stop_sample']-item['first_sample'], dtype='float64', always_2d=True)
            assert rate == 48000 and np.array_equal(clip, original)
            for milliseconds, observation in item['observations'].items():
                for filename, key in ((f'observations_{milliseconds}ms.npz', 'observations_sha256'),
                                      (f'observations_{milliseconds}ms.png', 'plot_sha256')):
                    assert sha(path.parent/filename) == observation[key]
        files = subprocess.check_output(['git', 'ls-files'], cwd=repo, text=True).splitlines()
        c_files = [name for name in files if Path(name).suffix.lower() in ('.c', '.h')]
        assert len(c_files) == 540
        subprocess.run(['git', 'diff', '--exit-code', 'HEAD', '--', 'src', 'modules',
                        'experiments', 'voices', 'CMakeLists.txt', 'Build-System.ps1'],
                       cwd=repo, check=True, capture_output=True)
        c_hashes = {name: sha(repo/name) for name in c_files}
        profiles = {name: sha(repo/name) for name in files if name.startswith('voices/')}
        save(final/'C_files_sha256.json', c_hashes)
        save(final/'voice_files_sha256.json', profiles)
        catalog_path = repo/'references/segments_v1.json'
        data_catalog = args.workspace/'references/segments_v1.json'
        assert catalog_path.read_bytes() == data_catalog.read_bytes()
        shutil.copy2(catalog_path, final/'catalog_before.json')
        catalog = load(catalog_path)
        annotations = 'research/E_low_state_v1_annotations.json'
        limits = ['exact ECU RPM or physical cycle order', 'warm-idle thermal state',
                  'pedal, torque, injector or clutch measurements', 'independent A/V or display latency',
                  'engine/background/recording-transfer separation']
        entries = {
            'E_exterior_stationary_intro_context': dict(seconds=[5, 20],
                perspective='exterior rear-left parked; handheld camera, adjacent roadway traffic',
                visual='Parked at sampled4.5..10.5s frames; brake lights change between7.5and8s samples',
                audio_interpretation='Approx33Hz family at5..8; pitch/level step near8; repeated rises/falls after10. Whole interval is not one steady idle.',
                allowed_uses=['stationary_context', 'exterior_spectral_observation', 'rev_sequence_context'],
                stationary_fit_status='Fixed5.2..7.8/root32.8/ref5,2,3/80ms coarse paths rejected; no phase or model. No interval/reference/window search to pass.'),
            'E_prelaunch_low_context': dict(seconds=[78, 79.25],
                perspective='cabin CORSA first gear after an edit',
                visual='Dash/phone zero speed, low nonzero tach bar; preceding77.75..78 edit changes mode/gear/time',
                audio_interpretation='Brief low family before rise; not independently verified stable warm idle',
                allowed_uses=['stationary_context', 'interior_spectral_observation']),
            'E_prelaunch_rise_departure_context': dict(seconds=[79.25, 83],
                perspective='cabin CORSA first gear',
                visual='Thrust mode mogelijk text, tach rise and hold around4500indicatedRPM, departure with disagreeing phone/dash speed',
                audio_interpretation='Rising/held/departure families; not an exact launch-control, torque-cut or clutch measurement',
                allowed_uses=['gear_display_context', 'interior_dynamic_observation'])}
        for name, item in entries.items():
            assert name not in catalog['segments']
            catalog['segments'][name] = dict(source='E', **item, evidence=annotations,
                                             not_established=limits, existing_audition=None)
        save(catalog_path, catalog)
        shutil.copy2(catalog_path, data_catalog)
        sources = [Path(__file__), catalog_path, repo/annotations,
                   repo/'research/E驻车与起步低转核查V1.md']
        sources += list(repo.glob('research/E_*v1*plan.json'))
        sources += [repo/'tools'/name for name in ('observe_source_states_v1.py',
                    'qualify_source_states_v1.py', 'audit_source_tracking_v1.py', 'inspect_idle_context_v1.py')]
        for source in sources:
            relative = source.relative_to(repo)
            target = final/'exact_sources'/relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            result['sources'][relative.as_posix()] = sha(source)
        result.update(result='source_context_bound_fixed_tracking_rejected', inspected_frames=frames,
            unchanged_reference_samples_verified=True, case=data['track_audit1']['cases']['exterior_before_blips'],
            C_files=540, C_hashes_sha256=sha(final/'C_files_sha256.json'),
            voices_hashes_sha256=sha(final/'voice_files_sha256.json'),
            runtime_changed=False, profiles_exported=0, timbre_accepted=False,
            idle_acceleration_complete=False, new_media_downloaded=False,
            existing_tests_rerun=False, moving35='held_unchanged',
            date='2026-11-13', next_step='Independent masked/sideband/missing-line/swept estimator validation before another predeclared real-source evaluation')
        save(summary_path, result)
    except Exception as exc:
        result.update(result='failed', error=repr(exc))
        raise
    finally:
        save(final/'report.json', result)
    print(json.dumps(dict(result=result['result'], frames=42, real_models=0, unchanged_C_H=540)), flush=True)
else:
    assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=repo).strip()
    summary = load(summary_path)
    assert summary['result'] == 'source_context_bound_fixed_tracking_rejected'
    assert sha(summary_path) == sha(final/'report.json')
    for item in summary['reports'].values():
        assert sha(args.workspace/item['path']) == item['sha256']
    for name, digest in summary['sources'].items():
        assert sha(repo/name) == sha(final/'exact_sources'/name) == digest
    for filename in ('C_files_sha256.json', 'voice_files_sha256.json'):
        for name, digest in load(final/filename).items():
            assert sha(repo/name) == digest
    out = args.workspace/'baselines/E_low_state_v1'
    out.mkdir(exist_ok=False)
    shutil.copytree(base, out/'evidence')
    shutil.copytree(args.workspace/'references/analysis/E_prelaunch_v1', out/'prelaunch_evidence')
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip()
    subprocess.run(['git', 'archive', '--format=zip', '--output='+str(out/'source.zip'), commit], cwd=repo, check=True)
    with zipfile.ZipFile(out/'source.zip') as archive:
        assert archive.testzip() is None
    (out/'README.txt').write_text('Fixed approved E observations and failed local tracking. No new model/runtime/timbre acceptance.\n'
        'All failed attempts and original audio/frames/executed sources retained. Goal remains incomplete.\n', encoding='utf-8')
    items = [dict(path=path.relative_to(out).as_posix(), bytes=path.stat().st_size, sha256=sha(path))
             for path in sorted(out.rglob('*')) if path.is_file()]
    save(out/'manifest.json', dict(schema='vsl.freeze/1', source_commit=commit, files=items,
        goal_complete=False, vehicle_timbre_accepted=False, real_profiles_exported=0,
        approved_source=load(repo/'references/segments_v1.json')['sources']['E']))
    for item in items:
        assert sha(out/item['path']) == item['sha256']
    print(json.dumps(dict(result='frozen', commit=commit, files=len(items),
                         bytes=sum(item['bytes'] for item in items))), flush=True)

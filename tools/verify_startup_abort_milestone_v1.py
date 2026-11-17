"""Audit startup interruption against preserved V4 audio and exact test bindings."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil

from startup_response_evidence_v1 import sha, verify


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    data = Path('E:/VehicleSoundLab')
    evidence = data/'renders/startup_abort_v1'
    analysis = data/'references/analysis/startup_abort_v1'
    previous = data/'baselines/exhaust_return_v1/delivery1'
    args.output.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, args.output/'executed_verification.py')
    reports = {name: read(evidence/name/'report.json') for name in
               ('baseline1', 'fixed3', 'regression3', 'ui3', 'stop-fixture2', 'web2', 'cycle-web2')}
    assert all(row['result'] == 'passed' for row in reports.values())
    old, new = reports['baseline1'], reports['fixed3']
    assert old['has_event_tail_after_OFF'] and old['OFF_event_peak'] > .19
    assert not new['has_event_tail_after_OFF'] and new['OFF_event_peak'] == 0
    assert next(x for x in new['event_lifetimes'] if x['type'] == 2)['end_frame'] == 22560
    assert next(x for x in old['event_lifetimes'] if x['type'] == 2)['end_frame'] == 167040
    regression = reports['regression3']
    assert len(regression['normal_original_v4_exact']) == 24 and len(regression['abort_cases']) == 3
    assert regression['manual_OFF_full_tail_exact']
    ui = reports['ui3']
    assert ui['two_start_cycles'] and ui['UI_queues_restart_until_OFF'] and ui['OFF_has_no_active_event']
    assert ui['actual_take_notice_and_final_state_replay_exact'] and ui['final_state']['underflows'] == 0
    assert reports['stop-fixture2']['STOP_natural_tail_preserved']['frame'] == 60000
    cycle = read(evidence/'cycle2/verification.json')
    assert cycle['passed'] and all(x['passed'] for x in cycle['checks'])
    assert cycle['frames'] == 1536000 and cycle['final_state']['lifecycle'] == 0
    assert cycle['final_state']['shifts'] == 9 and cycle['final_state']['overruns'] == 1
    assert len(cycle['afterfire_starts']) == 1
    final_bindings = []
    for name in ('fixed3', 'regression3', 'ui3', 'stop-fixture2', 'cycle2'):
        binding = read(evidence/name/'source_binding.json')
        verify(repo, binding)
        report = cycle if name == 'cycle2' else reports[name]
        assert sha(evidence/name/'source_binding.json') == report['source_binding_sha256']
        final_bindings.append(dict(name=name, files=len(binding['files']), bridge_sha256=binding['bridge_sha256']))
    binaries = {
        'source-v4': repo/'build-vehicle-source-v4/bin/Release/vsl_source_bridge.dll',
        'source-v5-before-queue-fix': evidence/'pre-queue-fix1/build-vehicle-source-v5/bin/Release/vsl_source_bridge.dll',
        'source-v5': repo/'build-vehicle-source-v5/bin/Release/vsl_source_bridge.dll',
        'event-author': repo/'build-event-synth-v1/bin/Release/vsl_event_author_bridge.dll',
    }
    assert sha(binaries['source-v4']) == sha(previous/'binaries/source-v4/vsl_source_bridge.dll')
    assert sha(binaries['event-author']) == sha(previous/'binaries/event-author/vsl_event_author_bridge.dll')
    assert sha(binaries['source-v5']) == new['bridge_sha256']
    binary_hashes = {sha(p) for p in binaries.values()}
    historical = []
    for folder in sorted(evidence.iterdir()):
        path = folder/'source_binding.json'
        if not path.is_file():
            continue
        binding = read(path)
        assert binding['bridge_sha256'] in binary_hashes, folder.name
        for row in binding['files']:
            assert sha(folder/'exact_sources'/row['path']) == row['sha256'], (folder.name, row['path'])
        historical.append(dict(name=folder.name, files=len(binding['files']), bridge_sha256=binding['bridge_sha256']))
    unchanged = {}
    changed = []
    for name in ('src', 'modules', 'voices'):
        count = 0
        for path in sorted((repo/name).rglob('*')):
            if not path.is_file() or (name != 'voices' and path.suffix not in ('.c', '.h')):
                continue
            relative = path.relative_to(repo)
            frozen = previous/'repo'/relative
            assert frozen.is_file(), str(relative)
            if sha(path) != sha(frozen):
                changed.append(relative.as_posix())
            else:
                count += 1
        unchanged[name] = count
    assert changed == ['modules/event_control/policy.c'], changed
    assert unchanged['voices'] == 89
    normal_cycle = []
    for name in ('mix.wav', 'native.wav'):
        current = evidence/'cycle2'/name
        frozen = previous/'evidence/cycle2'/name
        assert current.stat().st_size == frozen.stat().st_size and sha(current) == sha(frozen), name
        normal_cycle.append(dict(file=name, bytes=current.stat().st_size, sha256=sha(current), V4_exact=True))
    for name, script in (('web2', 'verify_startup_abort_web_v1.cjs'), ('cycle-web2', 'verify_exhaust_cycle_web_v1.cjs')):
        assert sha(evidence/name/'executed_verification.cjs') == reports[name]['verifier_sha256'] == sha(repo/'tools'/script)
    for log in ('build2.log', 'event-control-build2.log'):
        path = evidence/log
        assert '100% tests passed' in path.read_text(encoding='utf-8', errors='replace')
        shutil.copy2(path, args.output/log)
    assert '***Failed' in (evidence/'queue-regression1/test.log').read_text(encoding='utf-8')
    for name in ('experiments/event_synth_v1/control_checks.c', 'modules/event_control/policy.c'):
        path = args.output/'tested_sources'/name
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(repo/name, path)
    for name in ('event_control_checks', 'event_synth_checks'):
        shutil.copy2(repo/'build-event-control-stop-v1/bin/Release'/(name+'.exe'), args.output/(name+'.exe'))
    review = read(analysis/'review2/report.json')
    assert review['new']['bridge_sha256'] == new['bridge_sha256']
    for name, digest in review['files'].items():
        assert sha(analysis/'review2'/name) == digest
    assert sha(analysis/'review2/executed_build.py') == sha(repo/'tools/build_startup_abort_review_v1.py')
    assert sha(analysis/'review2/new-events.wav') == sha(evidence/'fixed3/events.wav')
    assert sha(analysis/'review2/new-mix.wav') == sha(evidence/'fixed3/mix.wav')
    assert sha(analysis/'cycle-review2/event-profile.json') == sha(previous/'analysis/cycle-review2/event-profile.json')
    report = dict(schema='vsl.startup-abort-milestone-audit/1', result='passed',
                  created=datetime.now(timezone.utc).isoformat(), goal_complete=False, timbre_accepted=False,
                  verifier_sha256=sha(__file__), previous_goal_turn='no progress: source-only budget clarification',
                  this_goal_turn='progress: fixed full automatic queue cancellation, completed source/UI/audio regressions and delivery',
                  old=old, fixed=new, regression=regression, ui=ui, stop_fixture=reports['stop-fixture2'],
                  cycle=cycle, web=reports['web2'], cycle_web=reports['cycle-web2'],
                  final_bindings=final_bindings, all_historical_exact_source_captures=historical,
                  binaries={k:dict(path=str(v), sha256=sha(v)) for k,v in binaries.items()},
                  runtime_C_changed=changed, unchanged_files=unchanged, normal_V4_full_cycle_exact=normal_cycle,
                  source_only=True, compute_optimization=False, new_downloads=False, commit_or_push=False,
                  persistent_updated_window_launched=False,
                  limitations=['Source A startup/catch remain unaccepted mixed-cabin candidates; no physical starter/combustion split or measured RPM.',
                               'Local E exhaust event is scoped1.2..14kHz only; afterfire identity and listening unconfirmed.',
                               'Full-band afterfire and engage/disengage/shift/stop formal sound profiles remain missing.',
                               'Bounded muted UI and selected source tests do not establish all cases or ADI timing.',
                               'Old V4 and pre-queue-fix V5 captures bind their own exact sources/binaries, not the current checkout.',
                               'Updated persistent launch/restart was previously rejected blocked by policy; no bypass.'])
    (args.output/'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps(dict(result='passed', unchanged=unchanged, changed=changed,
                         normal_cycle_exact=True, historical_bindings=len(historical), goal_complete=False)))


if __name__ == '__main__':
    main()

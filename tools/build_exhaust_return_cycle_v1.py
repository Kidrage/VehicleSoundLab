"""Use the local E event override through the full startup/drive/idle/stop chain."""
import argparse
import json
from pathlib import Path
import shutil
import sys


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--profile', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--review', type=Path, required=True)
    a = p.parse_args()
    sys.path.insert(0, 'E:/VehicleSoundLab/tools/python_deps')
    from vehicle_controller.native import Bridge
    from vehicle_controller import take, recipe
    from vehicle_scenarios.scenario import sport_lifecycle
    from vehicle_scenarios.capture import capture, replay
    from vehicle_scenarios.checks import inspect
    from vehicle_scenarios.review import build
    from startup_response_evidence_v1 import capture as bind, verify, sha
    repo = Path(__file__).resolve().parents[1]
    a.output.mkdir(parents=True, exist_ok=False)
    binding = bind(repo, a.output)
    bridge = Bridge(repo)
    doc = json.loads(a.profile.read_text(encoding='utf-8'))
    assert doc['kind'] == 'afterfire' and doc['physical_identity_confirmed'] is False
    overrides = {'afterfire': doc}
    value, scenario = sport_lifecycle(bridge, selection=0, event_overrides=overrides)
    take.save(a.output/'scenario.json', scenario)
    report, rows, transitions = capture(bridge, value, a.output)
    loaded = take.read(a.output/'lifecycle.vsltake.json', bridge)
    replayed = replay(bridge, loaded)
    checks = inspect(bridge, loaded, report, rows, replayed)
    starts = [e for e in value['source_events'] if e['type'] == 3 and e['action'] == 1]
    checks.append(dict(name='local_afterfire_triggered', passed=bool(starts), evidence=starts))
    checks.append(dict(name='requested_frames_exact', passed=all(e['frame'] == e['requested_frame'] for e in starts), evidence=starts))
    description = 'A crank/catch mixed-cabin candidates plus local E1.2..14kHz exhaust transient; physical afterfire identity/listening unconfirmed. No formal shift/engage/disengage/stop profiles.'
    report.update(schema='vsl.exhaust-return-cycle/1', bridge_sha256=bridge.sha256,
        voices_sha256=bridge.voices_sha256, checks=checks, passed=all(r['passed'] for r in checks),
        goal_complete=False, timbre_accepted=False, physical_identity_confirmed=False,
        afterfire_starts=starts, transitions=transitions,
        source_binding_sha256=sha(a.output/'source_binding.json'),
        event_profile_description=description,
        review_introduction='同一C驾驶器完成启动、怠速、加速、收油、制动回到怠速和熄火。收油接入E尾排1.2–14 kHz短声候选；启动与短声均待听评，换挡等其他独立短声仍缺。转速来自演示控制，并非素材实车轨迹。',
        review_listening_hint='先听完整干声，再切换独立事件：启动段为A候选，收油后为E尾排短声。可用“收油15.5s”按钮定位。各层保持相同增益，无房间处理。')
    take.save(a.output/'verification.json', report)
    if not report['passed']:raise AssertionError([r for r in checks if not r['passed']])
    build(a.output, a.review)
    take.save(a.review/'controller-preset.json', recipe.create(bridge, 0, value['initial'], '踏板驾驶', overrides))
    shutil.copy2(a.profile, a.review/'event-profile.json')
    shutil.copy2(__file__, a.output/'executed_build.py')
    verify(repo, binding)
    print(json.dumps(dict(passed=True, review=str(a.review), starts=len(starts), final=report['final_state']), ensure_ascii=False))


if __name__ == '__main__':main()

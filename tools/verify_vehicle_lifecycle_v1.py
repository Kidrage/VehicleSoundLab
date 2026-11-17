"""Generate a real-C full vehicle lifecycle with native sources and strict replay."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import traceback


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, 'E:/VehicleSoundLab/tools/python_deps')
    from vehicle_controller.native import Bridge
    from vehicle_controller import take
    from vehicle_scenarios.scenario import sport_lifecycle
    from vehicle_scenarios.capture import capture, replay
    from vehicle_scenarios.checks import inspect

    repo = Path(__file__).resolve().parents[1]
    exact = args.output/'exact_sources'
    files = [Path(__file__), *sorted((repo/'tools/vehicle_scenarios').glob('*.py')),
             *sorted((repo/'tools/vehicle_controller').glob('*.py'))]
    hashes = {}
    for path in files:
        relative = path.relative_to(repo)
        target = exact/relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        hashes[relative.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    bridge = Bridge(repo)
    value, scenario = sport_lifecycle(bridge)
    (args.output/'scenario.json').write_text(json.dumps(scenario, ensure_ascii=False, indent=2), encoding='utf-8')
    report, rows, transitions = capture(bridge, value, args.output)
    loaded = take.read(args.output/'lifecycle.vsltake.json', bridge)
    replayed = replay(bridge, loaded)
    checks = inspect(bridge, loaded, report, rows, replayed)
    report.update(schema='vsl.vehicle-lifecycle-verification/1', goal_complete=False,
                  timbre_accepted=False, bridge_sha256=bridge.sha256,
                  voices_sha256=bridge.voices_sha256, event_bank_sha256=bridge.event_bank_sha256,
                  available_event_mask=bridge.event_available_mask, exact_sources=hashes,
                  checks=checks, transitions=transitions,
                  missing_event_profiles=[name for k, name in enumerate(('engage','crank','catch','afterfire','shift','disengage','stop'))
                                          if not bridge.event_available_mask & (1 << k)],
                  sound_limits=['Startup candidates remain unaccepted mixed-cabin acoustic models.',
                                'Missing event profiles remain disabled; qualifying overrun is not audible new afterfire.',
                                'No independent RPM trajectory or physical starter/exhaust separation was established.',
                                'Offline generation/replay does not prove real-time device stability or ADI cycle count.'])
    report['passed'] = all(row['passed'] for row in checks)
    (args.output/'verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps(dict(passed=report['passed'], checks=[dict(name=x['name'],passed=x['passed']) for x in checks],
                         final=report['final_state']), ensure_ascii=False), flush=True)
    if not report['passed']:
        raise AssertionError('Failed full-lifecycle checks: ' + ', '.join(x['name'] for x in checks if not x['passed']))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        if '--output' in sys.argv:
            folder = Path(sys.argv[sys.argv.index('--output')+1])
            folder.mkdir(parents=True, exist_ok=True)
            (folder/'failure.txt').write_text(traceback.format_exc(), encoding='utf-8')
        raise

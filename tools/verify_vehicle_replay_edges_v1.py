"""A close pair of controls must preserve earlier event notices in one host block."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    repo = Path(__file__).resolve().parents[1]
    for relative in ('tools/verify_vehicle_replay_edges_v1.py', 'tools/vehicle_controller/take.py',
                     'tools/vehicle_controller/native.py'):
        target = args.output/'exact_sources'/relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(repo/relative, target)
    from vehicle_controller.native import Bridge, Engine
    from vehicle_controller import take
    bridge = Bridge(repo)
    control, _ = bridge.initial(0)
    control['events']['enabled'] = 1
    value = take.create(bridge, 0, control)
    control['events'].update(manual_type=2, manual_sequence=1)
    take.append(value, 137, control)
    control['gain'] = .3
    take.append(value, 211, control)
    value['frames'] = 960
    expected = []
    with Engine(bridge, 0) as engine:
        engine.set(value['initial'])
        chunks = [engine.process(137)]
        expected.extend(deepcopy(engine.last_events))
        engine.set(value['events'][0]['control'])
        chunks.append(engine.process(74))
        expected.extend(deepcopy(engine.last_events))
        engine.set(value['events'][1]['control'])
        chunks.append(engine.process(749))
        expected.extend(deepcopy(engine.last_events))
        state = engine.state()
    actual = []
    with Engine(bridge, 0) as engine:
        engine.set(value['initial'])
        a, index = take.replay_block(engine, value, 0, 480)
        actual.extend(deepcopy(engine.last_events))
        b, index = take.replay_block(engine, value, index, 480)
        actual.extend(deepcopy(engine.last_events))
        final = engine.state()
    report = dict(schema='vsl.vehicle-replay-edge-verification/1',
        bridge_sha256=bridge.sha256, voices_sha256=bridge.voices_sha256,
        controls=[137, 211], host_block=480, event_source='Existing real-A mixed catch candidate; no fixture installed.',
        expected_notices=expected, replay_notices=actual,
        exact_pcm=b''.join(chunks) == a+b, exact_state=state == final,
        exact_notices=expected == actual,
        take_sha256=hashlib.sha256((repo/'tools/vehicle_controller/take.py').read_bytes()).hexdigest(),
        goal_complete=False, timbre_accepted=False)
    (args.output/'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False), flush=True)
    assert expected and expected[0]['frame'] == 137
    assert report['exact_pcm'] and report['exact_state'] and report['exact_notices'], 'Replay lost an event notice across intra-block controls'


if __name__ == '__main__':
    main()

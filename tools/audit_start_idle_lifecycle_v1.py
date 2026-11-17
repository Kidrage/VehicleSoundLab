"""Independently compare every actual native process piece of both lifecycle takes."""
import argparse
import csv
from pathlib import Path
import shutil

import numpy as np
import soundfile as sf

from research_archive_v1 import load, save, sha
from vehicle_controller import take
from vehicle_controller.native import Bridge, Engine


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--evidence', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, args.output/'executed_audit.py')
    expected = load(args.evidence/'report.json')
    assert expected['result'] == 'passed'
    bridge = Bridge(Path(__file__).resolve().parents[1])
    assert bridge.sha256 == expected['bridge_sha256'] and bridge.channels() == 23
    report = dict(result='running', goal_complete=False, timbre_accepted=False)
    try:
        results = {}
        for name in ('main_only','idle_layer'):
            folder = args.evidence/name
            value = take.read(folder/'lifecycle.vsltake.json', bridge)
            notices = []
            calls = index = block = 0
            pattern = (1,1024,137,511,17,240,731)
            with sf.SoundFile(folder/'native.wav') as native, sf.SoundFile(folder/'mix.wav') as monitor:
                assert native.channels == 23 and monitor.channels == 2
                assert len(native) == len(monitor) == value['frames']
                with Engine(bridge, value['catalog']['id'], value['event_overrides'], value['startup_response'],
                            value.get('event_policy'), value.get('dna_bank')) as engine:
                    engine.set(value['initial'])
                    original = engine.process
                    def compare_piece(frames, solo=-1):
                        nonlocal calls
                        pcm = original(frames, solo)
                        actual = np.ctypeslib.as_array(engine.stems)[:frames*23].reshape(frames,23)
                        assert np.array_equal(actual, native.read(frames, dtype='float32', always_2d=True))
                        calls += 1
                        return pcm
                    engine.process = compare_piece
                    while engine.frame < value['frames']:
                        pcm,index = take.replay_block(engine, value, index, pattern[block%len(pattern)])
                        actual = np.frombuffer(pcm,dtype='<f4').reshape(-1,2)
                        assert np.array_equal(actual, monitor.read(len(actual), dtype='float32', always_2d=True))
                        notices.extend(engine.last_events)
                        block += 1
                    state = engine.state()
                assert native.tell() == monitor.tell() == value['frames']
            assert notices == value['source_events'] and state == expected['measurements'][name]['final_state']
            active, ids, peak = {},set(),0
            for row in notices:
                if row['action'] == 1:
                    assert row['reason'] == 0 and row['id'] not in ids and row['slot'] not in active
                    assert row['frame'] == row['requested_frame']
                    active[row['slot']] = (row['id'],row['type'])
                    ids.add(row['id']);peak=max(peak,len(active))
                else:
                    assert row['action'] == 2 and (row['reason'] == 0 or row['reason'] == 1 and row['type'] == 1)
                    assert active.pop(row['slot']) == (row['id'],row['type'])
            assert not active and peak == state['event_peak'] <= 4
            with (folder/'telemetry.csv').open(encoding='utf-8',newline='') as stream:
                rows = list(csv.DictReader(stream))
            early = [r for r in rows if 3 <= float(r['seconds']) < 5.5]
            parked = [r for r in rows if 31 <= float(r['seconds']) < 33.5]
            if name == 'idle_layer':
                assert all(float(r['idle_weight']) > .99 and float(r['rms_added']) > 0 for r in early+parked)
            else:
                assert max(float(r['idle_weight']) for r in rows) < 1e-15
            results[name] = dict(native_23channels_exact=True, monitor_exact=True, notices_state_exact=True,
                actual_native_process_calls=calls, host_blocks=block, frames=state['frame'], event_peak=peak,
                native_sha256=sha(folder/'native.wav'))
            print(name, 'every native piece exact', flush=True)
        with sf.SoundFile(args.evidence/'main_only/native.wav') as a, sf.SoundFile(args.evidence/'idle_layer/native.wav') as b:
            while a.tell() < len(a):
                x,y = a.read(4096,dtype='float32',always_2d=True),b.read(4096,dtype='float32',always_2d=True)
                assert np.array_equal(x[:,19:],y[:,19:])
        report.update(result='passed', cases=results, four_event_channels_exact_between_variants=True,
            actual_F2_idle_verified=True, physical_afterfire_confirmed=False, source_only=True)
    except Exception as error:
        report.update(result='failed',error=repr(error))
        raise
    finally:
        save(args.output/'report.json',report)


if __name__ == '__main__':
    main()

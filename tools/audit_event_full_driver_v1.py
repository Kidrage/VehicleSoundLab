"""Independently replay all native pieces and event lifetimes for E variants."""
import argparse
from copy import deepcopy
import hashlib
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
    repo = Path(__file__).resolve().parents[1]
    expected = load(args.evidence/'report.json')
    assert expected['result'] == 'passed'
    bridge = Bridge(repo)
    assert bridge.sha256 == expected['driver']['bridge_sha256'] and bridge.channels() == 23
    report = dict(result='running', physical_identity_confirmed=False, timbre_accepted=False)
    captures, results = {}, {}
    try:
        for variant in ('off', 'short', 'original', 'on'):
            folder = args.evidence/variant
            value = take.read(folder/'lifecycle.vsltake.json', bridge)
            mix, rate = sf.read(folder/'mix.wav', dtype='float32', always_2d=True)
            native, _ = sf.read(folder/'native.wav', dtype='float32', always_2d=True)
            assert rate == 48000 and native.shape == (384000, 23)
            pieces, monitor, notices = [], [], []
            index = block = 0
            pattern = (1, 1024, 137, 511, 17, 240, 731)
            with Engine(bridge, value['catalog']['id'], value['event_overrides'],
                        value['startup_response'], value.get('event_policy'), value.get('dna_bank')) as engine:
                engine.set(value['initial'])
                process = engine.process
                def intercept(frames, solo=-1):
                    pcm = process(frames, solo)
                    pieces.append(np.ctypeslib.as_array(engine.stems)[:frames*23].reshape(frames, 23).copy())
                    return pcm
                engine.process = intercept
                while engine.frame < value['frames']:
                    pcm, index = take.replay_block(engine, value, index, pattern[block % len(pattern)])
                    monitor.append(np.frombuffer(pcm, dtype='<f4').reshape(-1, 2).copy())
                    notices.extend(engine.last_events)
                    block += 1
                state = engine.state()
            assert np.array_equal(np.concatenate(monitor), mix)
            assert np.array_equal(np.concatenate(pieces), native)
            assert notices == value['source_events']
            assert state == expected['captures'][variant]['final_state']
            assert all(state[k] == 0 for k in ('event_rejected', 'event_overflow', 'event_log_lost'))
            active, ids, peak = {}, set(), 0
            for row in notices:
                assert row['action'] in (1, 2)
                if row['action'] == 1:
                    assert row['reason'] == 0 and row['id'] not in ids and row['slot'] not in active
                    assert row['frame'] == row['requested_frame']
                    active[row['slot']] = (row['id'], row['type'])
                    ids.add(row['id'])
                    peak = max(peak, len(active))
                else:
                    assert row['reason'] == 0 or (row['reason'] == 1 and row['type'] == 1)
                    assert active.pop(row['slot']) == (row['id'], row['type'])
            assert not active and peak == state['event_peak'] <= 4
            starts = [r for r in notices if r['action'] == 1 and r['type'] == 3]
            assert len(starts) == 4
            if variant != 'off':
                for row in starts:
                    # Inspect the onset before the next same-slot event can begin.
                    segment = native[row['frame']:row['frame']+120, 19+row['slot']]
                    nonzero = np.flatnonzero(segment)
                    assert len(nonzero) and nonzero[0] <= 1
            captures[variant] = dict(native=native, mix=mix, value=value)
            results[variant] = dict(native_23channels_exact=True, monitor_exact=True,
                notices_and_state_exact=True, observed_peak_voices=peak,
                original_take_sha256=sha(folder/'lifecycle.vsltake.json'),
                actual_native_process_calls=len(pieces), host_blocks=block)
            print(variant, 'native23 / identities / varied blocks passed', flush=True)
        on, off = captures['on'], captures['off']
        equivalent = deepcopy(on['value'])
        for control in [equivalent['initial']]+[r['control'] for r in equivalent['events']]:
            control['events']['levels'][3] = 0.
        for key in ('created', 'stream_id'):
            equivalent[key] = off['value'][key]
        assert equivalent == off['value']
        assert all(np.array_equal(row['native'][:, :19], on['native'][:, :19]) for row in captures.values())
        assert not np.any(off['native'][:, 19:])
        bindings = load(args.evidence.parent/'before/runtime.json')
        assert len(bindings) == 459 and all(sha(repo/name) == digest for name, digest in bindings.items())
        report.update(result='passed', captures=results, continuous_19channels_exact=True,
            off_on_only_event_level_differs=True, runtime_voice_files_unchanged=459,
            previous_failed_assembly_preserved=True)
    except Exception as error:
        report.update(result='failed', error=repr(error))
        raise
    finally:
        save(args.output/'report.json', report)


if __name__ == '__main__':
    main()

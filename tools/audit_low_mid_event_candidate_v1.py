"""Independently inspect immutable E candidate PCM, trigger notices and replay."""
import argparse
from copy import deepcopy
import hashlib
from pathlib import Path
import shutil

import numpy as np
import soundfile as sf

from event_authoring.model import synth
from event_authoring.native import Renderer
from research_archive_v1 import load, save, sha
from vehicle_controller import take
from vehicle_controller.native import Bridge, Engine


def pcm_digest(x):
    return hashlib.sha256(np.asarray(x, dtype='<f4').tobytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    out = args.output
    out.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, out/'executed_audit.py')
    repo = Path(__file__).resolve().parents[1]
    report = dict(result='running', timbre_accepted=False, physical_identity_confirmed=False,
                  goal_complete=False)
    try:
        old = load(args.evidence/'report.json')
        assert old['result'] == 'passed'
        doc = load(args.evidence/'event-profile.json')
        job = load(repo/'research/E_low_mid_event_v1.job.json')
        assert doc['source_job'] == job and doc['physical_identity_confirmed'] is False
        source = Path(job['source'])
        assert sha(source) == '3db9ceac1fc00d27a8ceb7abda88c3efa78efad2b11d4b9d2664ae287cb0f9bf'
        powers = {}
        with sf.SoundFile(source) as stream:
            assert stream.samplerate == 48000 and stream.channels == 2
            for key, interval in dict(event=[14.315, 14.415], before=[13.99, 14.19],
                                      after=[14.50, 14.70]).items():
                first, last = [round(t*48000) for t in interval]
                stream.seek(first)
                x = stream.read(last-first, dtype='float64', always_2d=True)
                assert len(x) == last-first and np.isfinite(x).all()
                powers[key] = sum(float(x[:, c] @ x[:, c]) for c in range(2))/(2*len(x))
                if key == 'event':
                    saved, rate = sf.read(args.evidence/'original-crop.wav', dtype='float64', always_2d=True)
                    assert rate == 48000 and np.array_equal(saved, x)
        contrasts = {key: float(10*np.log10(powers['event']/powers[key])) for key in ('before', 'after')}
        assert min(contrasts.values()) >= 3
        report['source'] = dict(sha256=sha(source), event_frames=[687120, 691920],
                                powers=powers, contrast_db=contrasts, original_crop_exact=True)
        renderer = Renderer(repo)
        seeds = []
        for seed in (27431, 48271, 93931, 17389):
            saved, rate = sf.read(args.evidence/f'C-{seed}.wav', dtype='float32')
            current, _ = renderer.render(doc['parameters'], doc['kind'], dict(seconds=.5, seed=seed))
            assert rate == 48000 and np.array_equal(saved, current)
            expected = synth(doc['parameters'], seed=seed, seconds=.5)
            expected = np.pad(expected, (0, len(saved)-len(expected)))
            error = float(np.max(abs(saved-expected)))
            assert error < 3e-7
            seeds.append(dict(seed=seed, actual_C_exact=True, independent_model_error_FS=error))
        report['C_seeds'] = seeds
        bridge = Bridge(repo)
        assert bridge.abi() == 11 and bridge.sha256 == old['driver']['bridge_sha256']
        captures = {}
        for variant in ('off', 'on'):
            value = take.read(args.evidence/f'drive-{variant}.take.json', bridge)
            monitor, rate = sf.read(args.evidence/f'drive-{variant}.wav', dtype='float32', always_2d=True)
            native, native_rate = sf.read(args.evidence/f'native-{variant}.wav', dtype='float32', always_2d=True)
            assert rate == native_rate == 48000 and monitor.shape == (384000, 2)
            assert native.shape == (384000, 23)
            notices, mix, stems = [], [], []
            pattern, block, index = (17, 1024, 137, 480, 511, 240), 0, 0
            with Engine(bridge, value['catalog']['id'], value['event_overrides'], value['startup_response'],
                        value['event_policy'], value.get('dna_bank')) as engine:
                engine.set(value['initial'])
                native_process = engine.process

                def observe(frames, solo=-1):
                    pcm = native_process(frames, solo)
                    # replay_block can split at a control change. The public
                    # scratch buffer only holds the LAST native piece, so copy
                    # every native call instead of reading it as a host block.
                    stems.append(np.ctypeslib.as_array(engine.stems)[:frames*23].reshape(frames, 23).copy())
                    return pcm

                engine.process = observe
                while engine.frame < value['frames']:
                    pcm, index = take.replay_block(engine, value, index, pattern[block % len(pattern)])
                    mix.append(np.frombuffer(pcm, dtype='<f4').reshape(-1, 2).copy())
                    notices.extend(engine.last_events)
                    block += 1
                state = engine.state()
                policy = engine.policy_stats()
            mix, stems = np.concatenate(mix), np.concatenate(stems)
            assert np.array_equal(mix, monitor) and np.array_equal(stems, native)
            assert np.isfinite(mix).all() and np.isfinite(stems).all()
            assert notices == value['source_events'] and state == old['driver']['final_state']
            assert all(state[k] == 0 for k in ('event_rejected', 'event_overflow', 'event_log_lost'))
            assert state['event_peak'] <= 4 and state['event_active'] == state['event_queue'] == 0
            active, ids, peak = {}, set(), 0
            for row in notices:
                assert row['action'] in (1, 2)
                if row['action'] == 1:
                    assert row['reason'] == 0
                    assert row['id'] not in ids and row['slot'] not in active
                    assert row['frame'] == row['requested_frame']
                    ids.add(row['id'])
                    active[row['slot']] = (row['id'], row['type'])
                    peak = max(peak, len(active))
                else:
                    assert row['reason'] == 0 or (row['reason'] == 1 and row['type'] == 1)
                    assert active.pop(row['slot']) == (row['id'], row['type'])
            assert not active and peak == state['event_peak'] <= 4
            captures[variant] = dict(mix=mix, native=native, take=value, notices=notices)
            report[variant] = dict(block_pattern=pattern, blocks=block, monitor_PCM_exact=True,
                native_23channels_exact=True, notices_exact=True, final_state=state,
                policy_stats=policy, pcm_sha256=pcm_digest(mix), observed_active_peak=peak)
        on, off = captures['on'], captures['off']
        equivalent = deepcopy(on['take'])
        for control in [equivalent['initial']]+[row['control'] for row in equivalent['events']]:
            control['events']['levels'][3] = 0.
        assert equivalent == off['take']
        assert np.array_equal(on['native'][:, :19], off['native'][:, :19])
        assert not np.any(off['native'][:, 19:])
        starts = [row for row in on['notices'] if row['type'] == 3 and row['action'] == 1]
        assert len(starts) == 4 and all(row['frame'] > 3.7*48000 for row in starts)
        onset_rows, mask = [], np.zeros(384000, dtype=bool)
        for row in starts:
            first, last = row['frame'], min(row['frame']+24000, 384000)
            mask[first:last] = True
            x = on['native'][first:last, 19+row['slot']]
            nonzero = np.flatnonzero(x)
            assert len(nonzero) and nonzero[0] <= 1
            onset_rows.append(dict(instance_id=row['id'], slot=row['slot'], requested_frame=first,
                                   first_nonzero_frame=first+int(nonzero[0]), peak=float(np.max(abs(x)))))
        assert not np.any(on['native'][~mask, 19:])
        event = on['native'][:, 19:].sum(axis=1)*2**-.5
        saved, _ = sf.read(args.evidence/'drive-events.wav', dtype='float32', always_2d=True)
        assert np.array_equal(saved, np.column_stack((event, event)))
        difference = float(np.max(abs(on['mix'].astype(float)-off['mix']-saved)))
        assert difference < 2e-7 and np.any(saved)
        binding = load(args.evidence.parent/'before/runtime.json')
        assert len(binding) == 459 and all(sha(repo/name) == digest for name, digest in binding.items())
        report.update(result='passed', afterfire_slot_starts=onset_rows,
            continuous_19channels_exact=True, event_only_mix_difference_FS=difference,
            runtime_voice_files_unchanged=459, source_ABI=11, bridge_sha256=bridge.sha256,
            evidence_report_sha256=sha(args.evidence/'report.json'),
            prior_audit1_failure='Auditor read only final native scratch piece for a split host block; fixed by observing each actual native process call, without changing runtime or saved evidence.',
            prior_audit2_failure='Auditor required natural termination for the gated crank. Explicit controller release is normal ES_RELEASED; only that crank termination accepts reason1. Rejections/replacements still fail.',
            executed_build_matches_current=sha(args.evidence/'executed_build.py') == sha(repo/'tools/build_low_mid_event_v1.py'))
    except Exception as error:
        report.update(result='failed', error=repr(error))
        raise
    finally:
        save(out/'report.json', report)
    print(dict(result='passed', starts=len(starts), native_variable_block_replay=True), flush=True)


if __name__ == '__main__':
    main()

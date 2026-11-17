"""Bounded offline native-C generation, identity-preserving replay and telemetry."""
import csv
import hashlib
import json
from pathlib import Path
import time

import numpy as np

from vehicle_controller.native import Engine
from vehicle_controller.render import FloatWav
from vehicle_controller import take
from .scenario import LIFECYCLE, OPERATING, RATE


def capture(bridge, value, output):
    """Capture every 200 Hz driver interval and every native sample/channel."""
    output = Path(output)
    width = bridge.channels()
    transitions = []
    rows = []
    digest = hashlib.sha256()
    value['source_events'] = []
    total_power = np.zeros(width)
    peaks = np.zeros(width)
    mix_peak = 0.
    reconstruction_error = 0.
    elapsed_start = time.perf_counter()
    monitor = FloatWav(output/'mix.wav', 2)
    native = FloatWav(output/'native.wav', width)
    offsets = np.cumsum([0] + [row['channels'] for row in bridge.stems])
    weights = np.concatenate([np.full(row['channels'], 1. if row['channels'] == 2 or row['name'] == 'legacy_event'
                             else 2**-.5) for row in bridge.stems])
    try:
        with Engine(bridge, value['catalog']['id'], value['event_overrides'],value['startup_response'],value.get('event_policy'),value.get('dna_bank')) as engine:
            engine.set(value['initial'])
            index = 0
            previous = None
            while engine.frame < value['frames']:
                while index < len(value['events']) and value['events'][index]['frame'] == engine.frame:
                    engine.set(value['events'][index]['control'])
                    index += 1
                first = engine.frame
                end = min(first + 240, value['frames'],
                          value['events'][index]['frame'] if index < len(value['events']) else value['frames'])
                frames = end - first
                pcm = engine.process(frames)
                x = np.frombuffer(pcm, dtype='<f4').reshape(-1, 2)
                stems = np.ctypeslib.as_array(engine.stems)[:frames * width].reshape(frames, width)
                if not (np.isfinite(x).all() and np.isfinite(stems).all()):
                    raise ValueError('Nonfinite native audio at frame ' + str(first))
                summed = np.zeros((frames, 2))
                for stem, a, b in zip(bridge.stems, offsets[:-1], offsets[1:]):
                    if stem['channels'] == 2:
                        summed += stems[:, a:b].astype(float)
                    else:
                        summed += stems[:, a:b].astype(float) * weights[a]
                reconstruction_error = max(reconstruction_error, float(np.max(abs(summed-x))))
                total_power += np.sum(stems.astype(float)**2, axis=0)
                peaks = np.maximum(peaks, np.max(abs(stems), axis=0))
                mix_peak = max(mix_peak, float(np.max(abs(x))))
                monitor.write(pcm)
                native.write(stems.tobytes())
                digest.update(pcm)
                value['source_events'].extend(engine.last_events)
                state = engine.state()
                state.update(first_frame=first, seconds=first/RATE,
                             lifecycle_name=LIFECYCLE[state['lifecycle']],
                             operating_name=OPERATING[state['operating']],
                             throttle_request=engine.controls['throttle'],
                             brake_request=engine.controls['brake'],
                             ignition_request=engine.controls['ignition'],
                             rms=float(np.sqrt(np.mean(x.astype(float)**2))),
                             peak=float(np.max(abs(x))))
                for stem, a, b in zip(bridge.stems, offsets[:-1], offsets[1:]):
                    state['rms_' + stem['name']] = float(np.sqrt(np.mean(stems[:, a:b].astype(float)**2)))
                rows.append(state)
                key = state['lifecycle'], state['operating'], state['gear']
                if key != previous:
                    transitions.append(dict(frame=first, seconds=first/RATE,
                        lifecycle=state['lifecycle_name'], operating=state['operating_name'],
                        gear=state['gear'], rpm=state['rpm'], speed_kph=3.6*state['speed_mps'],
                        shifts=state['shifts'], overruns=state['overruns']))
                    previous = key
                if end % (RATE * 4) == 0:
                    print(json.dumps(dict(generated_seconds=end/RATE, rpm=state['rpm'],
                        speed_kph=state['speed_mps']*3.6, state=state['operating_name'])), flush=True)
            final_state = engine.state()
    finally:
        monitor.close()
        native.close()
    take.save(output/'lifecycle.vsltake.json', value)
    with (output/'telemetry.csv').open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    with (output/'transitions.json').open('w', encoding='utf-8') as stream:
        json.dump(transitions, stream, ensure_ascii=False, indent=2, allow_nan=False)
    report = dict(pcm_sha256=digest.hexdigest(), frames=value['frames'],
                  native_channels=width, native_stems=bridge.stems,
                  native_rms_channels=np.sqrt(total_power/value['frames']).tolist(),
                  native_peak_channels=peaks.tolist(), monitor_peak=mix_peak,
                  native_reconstruction_error=reconstruction_error,
                  final_state=final_state, wall_seconds=time.perf_counter()-elapsed_start,
                  pc_timing_is_not_ADI_MCPS=True)
    return report, rows, transitions


def replay(bridge, value, block_pattern=(137, 511, 240, 1024, 17, 480)):
    """Exercise the actual live replay helper across control boundaries."""
    digest = hashlib.sha256()
    notices = []
    index = 0
    block = 0
    with Engine(bridge, value['catalog']['id'], value['event_overrides'],value['startup_response'],value.get('event_policy'),value.get('dna_bank')) as engine:
        engine.set(value['initial'])
        while engine.frame < value['frames']:
            pcm, index = take.replay_block(engine, value, index, block_pattern[block % len(block_pattern)])
            digest.update(pcm)
            notices.extend(engine.last_events)
            block += 1
        state = engine.state()
    return dict(pcm_sha256=digest.hexdigest(), source_events=notices,
                final_state=state, block_pattern=list(block_pattern), blocks=block)

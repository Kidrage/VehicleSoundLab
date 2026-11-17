"""Power accounting of isolated C stems; never estimates physical RPM."""
import csv
import json

import numpy as np
import soundfile as sf
from scipy import signal

BAND_EDGES = (0., 60., 300., 1200., 4500., 14000., 24000.)
MARKER_REGIONS = {'early': (0., .47), 'build': (.57, 1.37), 'settling': (1.60, 2.35)}


def marker_bands(x, early_seconds):
    """Observe fixed acoustic-marker windows; no matched-view quality score."""
    result = {}
    for name, (first, stop) in MARKER_REGIONS.items():
        a, b = round((early_seconds+first)*48000), round((early_seconds+stop)*48000)
        y = np.asarray(x[a:b], dtype=float)
        assert len(y) == b-a and a >= 0
        f, psd = signal.welch(y, fs=48000, nperseg=2048, noverlap=1024,
                             axis=0, detrend=False, scaling='density')
        bands = [psd[(f >= low) & ((f < high) if high < 24000 else (f <= high))].sum(axis=0)*(48000/2048)
                 for low, high in zip(BAND_EDGES[:-1], BAND_EDGES[1:])]
        result[name] = dict(first_frame=a, last_frame=b,
                            time_mean_power_LR=np.mean(y*y, axis=0).tolist(),
                            welch_band_power_LR=np.asarray(bands).tolist())
    return result


def stereo_groups(folder):
    report = json.loads((folder/'verification.json').read_text(encoding='utf-8'))
    native, rate = sf.read(folder/'native.wav', dtype='float32', always_2d=True)
    assert rate == 48000
    groups = {'continuous': np.zeros((len(native), 2)), 'events': np.zeros((len(native), 2))}
    offset = 0
    for row in report['native_stems']:
        channels = row['channels']
        x = native[:, offset:offset+channels].astype(float)
        if channels == 1:
            x = np.repeat(x, 2, axis=1) * (1. if row['name'] == 'legacy_event' else 2**-.5)
        group = 'events' if row['name'].startswith('event_') else 'continuous'
        groups[group] += x
        offset += channels
    assert offset == native.shape[1]
    mix, _ = sf.read(folder/'mix.wav', dtype='float32', always_2d=True)
    error = float(np.max(abs(groups['continuous']+groups['events']-mix)))
    assert error < 2e-6, error
    return groups, mix, native, report, error


def power(x):
    return float(np.mean(np.asarray(x, dtype=float)**2))


def observe(folder):
    groups, mix, native, verification, error = stereo_groups(folder)
    take = json.loads((folder/'lifecycle.vsltake.json').read_text(encoding='utf-8'))
    notices = take['source_events']
    starts = {row['type']: row['frame'] for row in notices if row['action'] == 1}
    regions = {}
    if 2 in starts:
        first = starts[2]
        stop = next(row['frame'] for row in notices if row['type'] == 2 and row['action'] == 2)
        cont = groups['continuous'][first:stop]
        event = groups['events'][first:stop]
        total = mix[first:stop]
        pc, pe, pt = power(cont), power(event), power(total)
        cross = float(2*np.mean(cont*event))
        regions['catch_event_active'] = dict(
            first_frame=first, last_frame=stop, seconds=[first/48000, stop/48000],
            continuous_power=pc, event_power=pe, twice_cross_power=cross, total_power=pt,
            power_identity_abs_error=abs(pc+pe+cross-pt),
            event_to_continuous_db=float(10*np.log10(pe/pc)) if pe and pc else None)
    with (folder/'telemetry.csv').open(encoding='utf-8', newline='') as stream:
        rows = list(csv.DictReader(stream))
    running = next(row for row in rows if row['lifecycle_name'] == 'RUNNING')
    idle = next(row for row in rows if row['lifecycle_name'] == 'RUNNING' and row['operating_name'] == 'IDLE')
    blocked = [row for row in rows if row['lifecycle_name'] == 'RUNNING'
               and row['operating_name'] in ('SHIFT_CUT', 'SHIFT_RECOVER')]
    return dict(
        variant=folder.name, verification_result=verification['result'],
        start_frames=starts, early_to_catch_seconds=(starts[2]-starts[1])/48000 if 1 in starts and 2 in starts else None,
        running_seconds=float(running['seconds']), idle_operating_seconds=float(idle['seconds']),
        startup_shift_block_seconds=len(blocked)*.005,
        idle_weight_first_positive_seconds=next(float(row['seconds']) for row in rows if float(row['idle_weight']) > 0),
        final_shift_count=int(rows[-1]['shifts']), reconstruction_max_error=error,
        regions=regions, final_rpm=float(rows[-1]['rpm']), rms=power(mix)**.5,
        acoustic_marker_band_edges_hz=list(BAND_EDGES),
        acoustic_marker_bands=marker_bands(mix, starts[1]/48000),
        physical_rpm_measured=False, listening_acceptance=False)

"""Read-only state diagnostics for the frozen 0.2.0 engine and approved A/B.

Band envelopes are observations of a recording, not separated engine stems,
pedal telemetry, or measured control time constants. No new audio is written.
"""
from pathlib import Path
import csv
import hashlib
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/python_deps'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import soundfile as sf
from scipy import signal
from PIL import Image, ImageDraw, ImageFont

OUT = ROOT / 'references/analysis/state_transitions_v1'
BANDS = [(28, 120), (120, 400), (400, 1200), (1200, 3000),
         (3000, 8000), (8000, 16000)]
CASES = [('A_start', 'A', 33, 40), ('A_stationary_revs', 'A', 238, 248),
         ('A_moving_exhaust', 'A', 316, 319.5),
         ('B_dynamic_cabin', 'B', 218, 230), ('B_release_candidate', 'B', 475, 485)]


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def band_envelopes(x, sr):
    # Average channel POWERS. Summing waveforms would cancel binaural content.
    assert sr == 48000
    freq, t, psd = signal.spectrogram(x.T, sr, window='hann', nperseg=4096,
        noverlap=4096 - 480, detrend=False, scaling='density', mode='psd')
    p = psd.mean(axis=0) * (sr / 4096)
    bands = np.array([p[(freq >= lo) & (freq < hi)].sum(axis=0)
                      for lo, hi in BANDS])
    total = p.sum(axis=0)
    assert np.isfinite(bands).all() and np.all(bands.sum(axis=0) <= total * (1 + 1e-10))
    return t, bands, total, freq, p


def envelope_events(t, powers):
    """Local spectral-energy peaks; event names require separate review."""
    activity = 10 * np.log10(np.maximum(powers[2:5].sum(axis=0), 1e-30))
    activity = np.convolve(np.pad(activity, (2, 2), mode='edge'),
                           np.ones(5) / 5, mode='valid')
    peaks, props = signal.find_peaks(activity, prominence=4, distance=40)
    events = []
    for index, prominence in zip(peaks, props['prominences']):
        if index < 30 or index > len(t) - 31:
            continue
        event = dict(anchor_source_seconds=float(t[index]),
                     detection_prominence_db=float(prominence), bands=[])
        for band, power in zip(BANDS, powers):
            lo, hi = max(0, index - 80), min(len(t), index + 81)
            peak_lo, peak_hi = max(lo, index - 15), min(hi, index + 16)
            top = peak_lo + int(np.argmax(power[peak_lo:peak_hi]))
            floor = float(np.percentile(power[lo:hi], 10))
            excursion = float(power[top] - floor)
            threshold = floor + excursion * .5
            before = np.flatnonzero(power[lo:top] <= threshold)
            after = np.flatnonzero(power[top + 1:hi] <= threshold)
            contrast = float(10 * np.log10(max(power[top], 1e-30) / max(floor, 1e-30)))
            valid = excursion > 0 and contrast >= 3
            rise = float(t[top] - t[lo + before[-1]]) if valid and len(before) else None
            fall = float(t[top + 1 + after[0]] - t[top]) if valid and len(after) else None
            event['bands'].append(dict(hz=list(band),
                local_peak_source_seconds=float(t[top]), contrast_db=contrast,
                half_excursion_rise_seconds=rise, half_excursion_fall_seconds=fall,
                rise_resolution=None if rise is None else ('below window resolution' if rise < 4096/48000 else 'window limited'),
                fall_resolution=None if fall is None else ('below window resolution' if fall < 4096/48000 else 'window limited'),
                status='observed' if rise is not None and fall is not None else 'low contrast or window censored'))
        events.append(event)
    return events


def reference_case(name, source, start, end):
    path = ROOT / f'references/clean/{source}_decoded_float.wav'
    with sf.SoundFile(path) as f:
        sr = f.samplerate
        assert f.channels == 2 and f.subtype == 'FLOAT'
        f.seek(round(start * sr))
        x = f.read(round((end - start) * sr), always_2d=True)
    t, p, total, freq, spectrum = band_envelopes(x, sr)
    t += start
    events = envelope_events(t, p)
    db = 10 * np.log10(np.maximum(p, 1e-30))
    fig, ax = plt.subplots(3, 1, figsize=(12, 9), sharex=True, constrained_layout=True)
    mask = (freq >= 28) & (freq <= 16000)
    sd = 10 * np.log10(np.maximum(spectrum[mask], 1e-30))
    ax[0].pcolormesh(t, freq[mask], sd, vmin=sd.max()-65, vmax=sd.max(),
                     shading='auto', cmap='magma', rasterized=True)
    ax[0].set_yscale('log')
    ax[0].set_ylabel('Hz (log)')
    ax[0].set_title(f'{name} | recording observations, not RPM / load telemetry')
    for band, level in zip(BANDS, db):
        label = f'{band[0]}-{band[1]} Hz'
        ax[1].plot(t, level, label=label, linewidth=1)
        ax[2].plot(t, level - level.max(), label=label, linewidth=1)
    ax[1].set_ylabel('Band power dBFS')
    ax[1].legend(ncol=3, fontsize=8)
    ax[2].set_ylabel('dB from each band peak')
    ax[2].set_ylim(-40, 1)
    ax[2].set_xlabel('Source seconds | 85.3 ms analysis window / 10 ms hop')
    for event in events:
        for axis in ax:
            axis.axvline(event['anchor_source_seconds'], color='grey', alpha=.35, linewidth=.7)
    for axis in ax[1:]:
        axis.grid(alpha=.15)
    fig.savefig(OUT / f'{name}.png', dpi=150)
    plt.close(fig)
    with (OUT / f'{name}.csv').open('w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['source_seconds'] + [f'{lo}_{hi}_dbfs' for lo, hi in BANDS])
        writer.writerows(zip(t, *db))
    return dict(name=name, source=source, range_seconds=[start, end],
                channels=2, channel_policy='mean of powers; no waveform folding',
                band_peak_dbfs=db.max(axis=1).tolist(),
                energy_peak_candidates=events, plot=f'{name}.png', data=f'{name}.csv')


def matched_rpm_metrics():
    rows = []
    for name, load in [('light', .12), ('loaded', .85), ('overrun', -.4)]:
        path = ROOT / f'renders/v0.2.0/v10_5000_{name}.wav'
        x, sr = sf.read(path, always_2d=True, start=3*48000, stop=int(5.5*48000))
        _, p, total, _, _ = band_envelopes(x, sr)
        rows.append(dict(case=name, target_rpm=5000, signed_load=load,
            source=str(path.relative_to(ROOT)), sha256=digest(path),
            measurement_file_seconds=[3, 5.5],
            rms_dbfs=float(10*np.log10(np.mean(x*x))),
            band_energy_fraction=(p.sum(axis=1)/total.sum()).tolist()))
    return rows


def coast_shift_observations():
    path = ROOT / 'renders/v0.2.0/v10_drive_trace.csv'
    rows = list(csv.DictReader(path.open(encoding='utf-8')))
    changes = []
    for prev, row in zip(rows, rows[1:]):
        if int(row['shifts']) > int(prev['shifts']) and float(row['throttle']) < .65 and int(row['gear']) > int(prev['gear']):
            changes.append(row)
    return dict(trace=str(path.relative_to(ROOT)), trace_sha256=digest(path),
                scope='Observed demo upshifts below 0.65 filtered pedal. Policy choice, not verified vehicle behaviour.',
                events=changes)


def start_and_road_context():
    times = [35.8, 36.2, 36.6, 37.0, 37.4, 37.8, 317.8, 318.2, 318.6]
    board = Image.new('RGB', (1200, 750), (20, 25, 34))
    draw = ImageDraw.Draw(board)
    font = ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf', 17)
    for i, seconds in enumerate(times):
        frame = OUT / f'A_frame_{seconds:.1f}.jpg'
        subprocess.run(['D:/repo/tools/ffmpeg/bin/ffmpeg.exe', '-v', 'error',
            '-nostdin', '-y', '-ss', str(seconds), '-i',
            str(ROOT / 'references/raw/A_context_360p.mp4'),
            '-frames:v', '1', str(frame)], check=True)
        with Image.open(frame) as im:
            im.thumbnail((400, 225))
            x, y = i % 3 * 400, i // 3 * 250
            board.paste(im, (x, y))
            draw.text((x+8, y+226), f'A source {seconds:.1f} s', font=font, fill='white')
    board.save(OUT / 'A_start_and_road_context.jpg')
    return dict(video='references/raw/A_context_360p.mp4',
                video_sha256=digest(ROOT / 'references/raw/A_context_360p.mp4'),
                frame_source_seconds=times, contact_sheet='A_start_and_road_context.jpg',
                limitation='Visible action/context only; 360p does not establish numeric RPM or exact combustion timing.')


def moving_band_change():
    # Two explicitly stated recording windows, not inferred pedal states.
    path = OUT / 'A_moving_exhaust.csv'
    rows = list(csv.DictReader(path.open(encoding='utf-8')))
    windows = [(317.75, 317.90), (318.18, 318.33)]
    powers = []
    for lo, hi in windows:
        selected = [r for r in rows if lo <= float(r['source_seconds']) < hi]
        powers.append(np.array([[10**(float(r[f'{a}_{b}_dbfs'])/10)
                                for a, b in BANDS] for r in selected]).mean(axis=0))
    return dict(source='A', before_source_seconds=windows[0], after_source_seconds=windows[1],
                after_minus_before_band_db=(10*np.log10(powers[1]/powers[0])).tolist(),
                meaning='Change in mean recording band power; not separated exhaust/intake/body response or known pedal release.')


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    ledger = json.loads((ROOT / 'references/approval_manifest.json').read_text(encoding='utf-8'))
    for source in ['A', 'B']:
        assert next(x for x in ledger if x['id'] == source)['approved'] is True
    report = dict(schema='vsl.state-transitions/1', runtime_version='0.2.0',
        analysis_only=True, script_sha256=digest(Path(__file__)), bands_hz=BANDS,
        analysis=dict(window_frames=4096, hop_frames=480, sample_rate=48000,
            timing_resolution_warning='85.3 ms window smears edges. 10 ms hop is not 10 ms event accuracy.',
            peak_measurement='400-8000 Hz energy anchors, 4 dB prominence; per-band maxima within +/-150 ms; 10th percentile floor within +/-800 ms; half-excursion power crossing.',
            limits=['No source separation, absolute RPM/load, ignition or gear telemetry.',
                    'Auto energy peaks are not confirmed rev, backfire or shift events.',
                    'Envelope crossing times are not physical attack/release constants.',
                    'Same-recording exploratory observations; no held-out model validation.',
                    'B has no inspected video. Recording processing and spatial context can change envelopes.']),
        sources={source: dict(master=f'references/clean/{source}_decoded_float.wav',
            sha256=digest(ROOT / f'references/clean/{source}_decoded_float.wav'))
            for source in ['A', 'B']},
        references=[reference_case(*case) for case in CASES],
        matched_5000_rpm=matched_rpm_metrics(),
        coast_shift_observations=coast_shift_observations(),
        video_context=start_and_road_context(), moving_band_change=moving_band_change())
    report['outputs'] = {p.name: digest(p) for p in sorted(OUT.iterdir())
                         if p.suffix in ['.png', '.csv', '.jpg']}
    (OUT / 'results.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    for row in report['references']:
        print(row['name'], 'energy peaks:', [round(e['anchor_source_seconds'], 3) for e in row['energy_peak_candidates']])
    for row in report['matched_5000_rpm']:
        print(row['case'], 'RMS', round(row['rms_dbfs'], 2),
              '3-8 kHz fraction', round(row['band_energy_fraction'][4], 7))


if __name__ == '__main__':
    main()

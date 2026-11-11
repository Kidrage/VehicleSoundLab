"""Export tracked AM/cubic-phase intervals, without waveform tables.

The legacy detector is deliberately retained for archive recovery. New excerpts
use shared-frequency stereo detection. L/R remain recording channels, not banks.
"""
from dataclasses import asdict
import numpy as np
from scipy.optimize import linear_sum_assignment
from sinusoidal_experiment import add_interval, peaks
from osc_research.tracker import Settings, candidates


def channel_coefficients(left, right, frames, rate):
    fa, aa, pa = left
    fb, ab, pb = right
    duration = frames / rate
    predicted = pa + np.pi * (fa + fb) * duration
    pb += 2 * np.pi * round((predicted-pb) / (2*np.pi))
    delta, wa, wb = pb-pa, 2*np.pi*fa, 2*np.pi*fb
    return [aa, ab, pa, wa,
        (3*delta-(2*wa+wb)*duration)/duration**2,
        (-2*delta+(wa+wb)*duration)/duration**3]


def fit(audio, rate, count=64, settings=Settings(), legacy=False, group=0):
    audio = np.asarray(audio)
    if audio.ndim == 1:
        audio = np.column_stack([audio, audio])
    if audio.shape[1] != 2:
        raise ValueError('Stereo input required')
    out, segments = np.zeros_like(audio), {}
    previous = None
    old_center = None
    matched = born = died = observed = 0
    rates, changes = [], []
    half, hop = settings.window//2, settings.hop

    def interval(start, left, right):
        coefficients = []
        for channel in range(2):
            ix = [0, 1+channel*2, 2+channel*2]
            a, b = left[ix], right[ix]
            # Independent legacy vector formula is the Python render oracle.
            add_interval(out[:, channel], start, hop, rate, a, b)
            coefficients.extend(channel_coefficients(a, b, hop, rate))
        segments.setdefault(start, []).append([group, *coefficients])

    for center in range(half, len(audio)-half, hop):
        frame = audio[center-half:center+half]
        if legacy:
            mono = peaks(frame[:, 0], rate, count)
            current = mono[:, [0, 1, 2, 1, 2]]
        else:
            current = candidates(frame, rate, count, settings)
        observed += len(current)
        if previous is not None:
            used_a, used_b = set(), set()
            if len(previous) and len(current):
                cost = abs(previous[:, None, 0]-current[None, :, 0]) / np.maximum(
                    16, previous[:, None, 0]*.045)
                rows, cols = linear_sum_assignment(cost)
                for i, j in zip(rows, cols):
                    if cost[i, j] > 1:
                        continue
                    interval(old_center, previous[i], current[j])
                    used_a.add(i)
                    used_b.add(j)
                    matched += 1
                    rates.append(abs(current[j, 0]-previous[i, 0])*rate/hop)
                    aa = np.linalg.norm(previous[i, 1::2])
                    ab = np.linalg.norm(current[j, 1::2])
                    if min(aa, ab) > 1e-8:
                        changes.append(abs(20*np.log10(ab/aa)))
            for i, a in enumerate(previous):
                if i not in used_a:
                    end = a.copy()
                    end[1::2] = 0
                    end[2::2] += 2*np.pi*a[0]*hop/rate
                    interval(old_center, a, end)
                    died += 1
            for j, b in enumerate(current):
                if j not in used_b:
                    start = b.copy()
                    start[1::2] = 0
                    start[2::2] -= 2*np.pi*b[0]*hop/rate
                    interval(old_center, start, b)
                    born += 1
        previous, old_center = current, center
    frames = len(range(half, len(audio)-half, hop))
    stats = dict(settings=asdict(settings), legacy=legacy, support_limit=count,
        mean_detected_support=observed/max(frames, 1), analysed_frames=frames,
        matched=matched, births=born, deaths=died,
        frequency_step_hz_per_second_p50_p90=np.percentile(rates, [50, 90]).tolist() if rates else [],
        amplitude_step_db_per_hop_p50_p90=np.percentile(changes, [50, 90]).tolist() if changes else [],
        interpretation='Descriptive detector-track changes; includes estimation errors, source pitch, microphone/space and transients. Not identified ignition jitter or mechanical modes.')
    return out, segments, stats


def write_model(path, rate, frames, *groups, hop=256):
    starts = sorted(set().union(*(group.keys() for group in groups)))
    with path.open('w', encoding='ascii', newline='\n') as file:
        file.write(f'VSL_REFERENCE_OSC 1 {rate} {frames} {len(starts)}\n')
        for start in starts:
            rows = [row for group in groups for row in group.get(start, [])]
            if len(rows) > 256:
                raise ValueError('C per-segment row budget exceeded')
            file.write(f'{start} {hop} {len(rows)}\n')
            for row in rows:
                file.write(str(row[0])+' '+' '.join(format(v, '.17g') for v in row[1:])+'\n')
    return dict(segments=len(starts), maximum_rows=max(
        sum(len(group.get(start, [])) for group in groups) for start in starts),
        representation='AM endpoints and cubic phase coefficients; no PCM or residual waveform')

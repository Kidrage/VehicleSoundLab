"""Versioned tracked fit. Preserve legacy row order and retain track identity."""
import numpy as np
from scipy.optimize import linear_sum_assignment
from sinusoidal_experiment import peaks, add_interval
from osc_research.tracker import candidates, Settings
from reference_osc_v1.exporter import channel_coefficients, write_model


def fit(audio, rate, count=64, settings=Settings(), legacy=False, group=0, id_start=0):
    if audio.ndim == 1:
        audio = np.column_stack([audio, audio])
    out, segments = np.zeros_like(audio), {}
    previous = None
    previous_ids = None
    old_center = None
    next_id = id_start
    counts = dict(matched=0, born=0, died=0)
    half, hop = settings.window//2, settings.hop

    def interval(start, a, b, identity):
        row = [group]
        for channel in range(2):
            indices = [0, 1+channel*2, 2+channel*2]
            left, right = a[indices], b[indices]
            add_interval(out[:, channel], start, hop, rate, left, right)
            row += channel_coefficients(left, right, hop, rate)
        segments.setdefault(start, []).append((identity, row))

    for center in range(half, len(audio)-half, hop):
        frame = audio[center-half:center+half]
        if legacy:
            mono = peaks(frame[:, 0], rate, count)
            current = mono[:, [0, 1, 2, 1, 2]]
        else:
            current = candidates(frame, rate, count, settings)
        current_ids = [None]*len(current)
        if previous is not None:
            used_a, used_b = set(), set()
            if len(previous) and len(current):
                cost = abs(previous[:, None, 0]-current[None, :, 0])/np.maximum(16, previous[:, None, 0]*.045)
                rows, cols = linear_sum_assignment(cost)
                for i, j in zip(rows, cols):
                    if cost[i, j] > 1:
                        continue
                    identity = previous_ids[i]
                    interval(old_center, previous[i], current[j], identity)
                    current_ids[j] = identity
                    used_a.add(i)
                    used_b.add(j)
                    counts['matched'] += 1
            for i, a in enumerate(previous):
                if i not in used_a:
                    b = a.copy()
                    b[1::2] = 0
                    b[2::2] += 2*np.pi*a[0]*hop/rate
                    interval(old_center, a, b, previous_ids[i])
                    counts['died'] += 1
            for j, b in enumerate(current):
                if j not in used_b:
                    a = b.copy()
                    a[1::2] = 0
                    a[2::2] -= 2*np.pi*b[0]*hop/rate
                    current_ids[j] = next_id
                    next_id += 1
                    interval(old_center, a, b, current_ids[j])
                    counts['born'] += 1
        else:
            current_ids = list(range(next_id, next_id+len(current)))
            next_id += len(current)
        previous, previous_ids, old_center = current, current_ids, center
    return out, segments, dict(**counts, assigned_track_ids=next_id-id_start), next_id


def export(model_path, id_path, rate, frames, *groups):
    plain = [{start:[row for identity, row in rows] for start, rows in group.items()} for group in groups]
    stats = write_model(model_path, rate, frames, *plain)
    starts = sorted(set().union(*(group.keys() for group in groups)))
    used = sorted({identity for group in groups for rows in group.values() for identity, row in rows})
    remap = {identity:i for i, identity in enumerate(used)}
    total = sum(len(rows) for group in groups for rows in group.values())
    with id_path.open('w', encoding='ascii', newline='\n') as file:
        file.write(f'VSL_OSC_IDS 1 {len(starts)} {len(used)} {total}\n')
        for start in starts:
            identities = [remap[identity] for group in groups for identity, row in group.get(start, [])]
            file.write(f'{start} 256 {len(identities)}\n')
            file.write(' '.join(map(str, identities))+'\n')
    return dict(**stats, persistent_tracks=len(used), total_rows=total)

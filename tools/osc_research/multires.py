"""Two-resolution shared stereo analysis with an explicit trajectory budget.

The older tracker module remains unchanged to preserve its research hashes.
Overlap candidates share a frame centre and are merged as complex L/R gains.
This is still an excerpt fit, not a procedural source model.
"""
from dataclasses import replace
import numpy as np
from scipy.optimize import linear_sum_assignment
from .tracker import Settings, candidates, render_interval

LONG = Settings(window=4096, lower_hz=28, upper_hz=1700)
SHORT = Settings(window=2048, lower_hz=700, upper_hz=14000)
QUOTAS = [(28, 400, 8), (400, 1600, 16), (1600, 5000, 24), (5000, 14001, 16)]


def complex_gains(row):
    return row[1::2]*np.exp(1j*row[2::2])


def high_weight(f):
    u = np.clip((f-800)/800, 0, 1)
    return u*u*(3-2*u)


def extract(audio, center, sr, balanced=False):
    def get(setting):
        half = setting.window//2
        return candidates(audio[center-half:center+half], sr, 128, setting)
    low, high = get(LONG), get(SHORT)
    merged, used_low, used_high = [], set(), set()
    if len(low) and len(high):
        cost = abs(low[:, None, 0]-high[None, :, 0])/25
        rows, cols = linear_sum_assignment(cost)
        for i, j in zip(rows, cols):
            if cost[i, j] > 1 or not (700 <= low[i, 0] <= 1700):
                continue
            w = high_weight((low[i, 0]+high[j, 0])*.5)
            z = (1-w)*complex_gains(low[i])+w*complex_gains(high[j])
            row = low[i].copy()
            row[0] = (1-w)*low[i, 0]+w*high[j, 0]
            row[1::2], row[2::2] = abs(z), np.angle(z)
            merged.append(row)
            used_low.add(i)
            used_high.add(j)
    for group, used, is_high in [(low, used_low, False), (high, used_high, True)]:
        for i, row in enumerate(group):
            if i in used:
                continue
            w = high_weight(row[0])
            row = row.copy()
            row[1::2] *= w if is_high else 1-w
            if np.sum(row[1::2]**2) > 1e-24:
                merged.append(row)
    merged = np.array(merged).reshape(-1, 1+audio.shape[1]*2)
    if not len(merged):
        return merged
    power = np.sum(merged[:, 1::2]**2, axis=1)
    ranked = np.argsort(power)[::-1]
    if not balanced:
        return merged[ranked[:64]]
    selected = []
    for lo, hi, quota in QUOTAS:
        selected.extend([i for i in ranked if lo <= merged[i, 0] < hi][:quota])
    seen = set(selected)
    selected.extend([i for i in ranked if i not in seen][:64-len(selected)])
    return merged[selected]


def synthesize(audio, sr, balanced=False):
    out = np.zeros_like(audio, dtype=float)
    hop = 256
    previous = None
    old_center = 0
    births = deaths = support = frames = 0
    for center in range(LONG.window//2, len(audio)-LONG.window//2, hop):
        current = extract(audio, center, sr, balanced)
        frames += 1
        support += len(current)
        if previous is not None:
            used_a, used_b = set(), set()
            if len(previous) and len(current):
                cost = abs(previous[:, None, 0]-current[None, :, 0])/np.maximum(16, previous[:, None, 0]*.045)
                rows, cols = linear_sum_assignment(cost)
                for i, j in zip(rows, cols):
                    if cost[i, j] <= 1:
                        render_interval(out, old_center, sr, hop, previous[i], current[j])
                        used_a.add(i)
                        used_b.add(j)
            for group, used, end in [(previous, used_a, True), (current, used_b, False)]:
                for i, row in enumerate(group):
                    if i in used:
                        continue
                    zero = row.copy()
                    zero[1::2] = 0
                    zero[2::2] += (1 if end else -1)*2*np.pi*row[0]*hop/sr
                    render_interval(out, old_center, sr, hop, row if end else zero, zero if end else row)
                    deaths += int(end)
                    births += int(not end)
        previous, old_center = current, center
    return out, dict(mean_support_per_frame=support/max(1, frames), births=births, deaths=deaths,
                     maximum_shared_frequencies=64, maximum_channel_oscillators=128)

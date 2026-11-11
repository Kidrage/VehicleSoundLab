"""Compare old four-cycle phase reading and local joint projection on known sweeps."""
import argparse
import json
from pathlib import Path
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace', required=True, type=Path)
parser.add_argument('--out', required=True, type=Path)
parser.add_argument('--method',choices=('short','debiased'),default='short')
args = parser.parse_args()
sys.path.insert(0, str(args.workspace / 'tools/python_deps'))
import numpy as np
from drive_evidence_v1.sources import sha
from exterior_clock_v1.warp import warp, polish as old_polish
from phase_clock_v1.projection import polish as short_polish
from phase_clock_v1.debiased import polish as debiased_polish
polish=short_polish if args.method=='short' else debiased_polish
from sound_dna.windowed import coefficients
from state_colour_v2.features import shape_delta, select_windows, BANDS
from state_colour_v2.clock import follow
from shift_evidence_v1.spectrum import observe

args.out.mkdir(parents=True, exist_ok=False)
clock_path = args.workspace / 'references/analysis/state_colour_v2/clocks_attempt2/report.json'
clocks = json.loads(clock_path.read_text(encoding='utf-8'))
orders = np.arange(1, 289)
centers = np.sqrt(np.array(BANDS)[:, 0] * np.array(BANDS)[:, 1]) / 46.875
known_gain = 10 ** (np.interp(np.log2(orders), np.log2(centers), [-5, -3, 2, 4, 6]) / 20)
amp = .03 / (1 + (orders / 12) ** 1.3)
phase = .2 * np.sin(orders)
z = amp[:, None] * np.exp(1j * np.column_stack((phase, phase + .4 * np.sin(orders * .3))))
z[:, 1] *= .8 + .1 * np.sin(orders)
z[[2, 4, 6]] *= np.array([3., 6., 2.])[:, None]


def source(rows, gain):
    times = np.array([r['seconds'] for r in rows]);roots = np.array([r['root_hz'] for r in rows])
    start = np.floor((times[0] - .2) * 48000) / 48000
    t = start + np.arange(int(np.ceil((times[-1] + .2 - start) * 48000))) / 48000
    hz = np.interp(t, times, roots)
    cycle = np.r_[0., np.cumsum((hz[1:] + hz[:-1]) / 96000)]
    audio = np.zeros((len(t), 2))
    for h in range(288):
        audio += np.real(np.exp(2j * np.pi * (h + 1) * cycle)[:, None] * z[h] * gain[h])
    return audio, start, times, roots


def measure(audio, source_start, times, roots, rising, method):
    initial, positions, raw = warp(audio, source_start, times, roots, times[0], times[-1])
    normalized, where, evidence = method(audio, source_start, initial, positions, 5, raw['source_cutoff_hz'])
    rows = coefficients(normalized, 288).reshape(-1, 288, 4)
    rows = rows[:, :, ::2] + 1j * rows[:, :, 1::2]
    center = np.arange(len(rows)) * 256 + 2048
    roots_at = np.interp(center, np.arange(len(where)), 1 / (1024 * np.gradient(where)))
    seconds_at = np.interp(center, np.arange(len(where)), where)
    keep = select_windows(dict(window_root_hz=roots_at, window_source_seconds=seconds_at), rising)
    if not keep.any(): raise ValueError('No selected window')
    return np.mean(abs(rows[keep]) ** 2, axis=0), dict(selected=int(keep.sum()), **evidence)


report = dict(schema='vsl.phase-clock-exploration/1', method=args.method, pairs=[], cases=[], parameters='Explicit refiner; FFT tracker unchanged')
power = {}
for pair in (1, 2, 4):
    for kind in ('rise', 'fall'):
        name = kind + str(pair)
        audio, start, times, roots = source(clocks['cases'][name]['5']['rows'], np.ones(288))
        spectrum = observe(audio, start, 80, hop=240)
        tracked = follow(spectrum['hz'], spectrum['seconds'], spectrum['power_low'], times[0], times[-1], roots[0], 5)
        assert tracked['rows']
        at = np.array([r['seconds'] for r in tracked['rows']]);observed = np.array([r['root_hz'] for r in tracked['rows']])
        for label, method in [('legacy', old_polish), ('local', polish)]:
            power[name, label], evidence = measure(audio, start, at, observed, kind == 'rise', method)
            report['cases'].append(dict(case=name, method=label, **evidence))
        changed, _, _, _ = source(clocks['cases'][name]['5']['rows'], known_gain if kind == 'rise' else np.ones(288))
        power[name, 'known'], _ = measure(changed, start, at, observed, kind == 'rise', polish)
    row = dict(pair=pair)
    for label in ('legacy', 'local'):
        delta = shape_delta(power['fall'+str(pair), label], power['rise'+str(pair), label]).mean(axis=1)
        row[label+'_zero_shape_error_db'] = delta.tolist()
    expected = shape_delta(abs(z)**2, abs(z*known_gain[:, None])**2).mean(axis=1)
    measured = shape_delta(power['fall'+str(pair), 'known'], power['rise'+str(pair), 'known']).mean(axis=1)
    row['local_known_shape_error_db'] = (measured-expected).tolist()
    report['pairs'].append(row)
    print(json.dumps(row), flush=True)
report['clocks_sha256'] = sha(clock_path)
repo=Path(__file__).resolve().parents[1]
report['source_sha256']={p.relative_to(repo).as_posix():sha(p) for p in (Path(__file__),repo/'tools/phase_clock_v1/projection.py',repo/'tools/phase_clock_v1/debiased.py',repo/'tools/exterior_clock_v1/warp.py',repo/'tools/state_colour_v2/clock.py',repo/'tools/state_colour_v2/features.py',repo/'tools/sound_dna/windowed.py')}
(args.out/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')

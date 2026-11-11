"""Known swept OSC controls for four-cycle rise/fall colour observations."""
import argparse
import json
import sys
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace', type=Path, required=True)
parser.add_argument('--clocks', type=Path, required=True)
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()
sys.path.insert(0, str(args.workspace / 'tools/python_deps'))
import numpy as np
from drive_evidence_v1.sources import sha
from state_dna_v1.compare import describe
from state_colour_v2.features import BANDS, shape_delta, select_windows
from state_colour_v2.clock import follow
from shift_evidence_v1.spectrum import observe

args.out.mkdir(parents=True, exist_ok=False)
clocks = json.loads((args.clocks / 'report.json').read_text())
orders = np.arange(1, 289)
centers = np.sqrt(np.array(BANDS)[:, 0] * np.array(BANDS)[:, 1]) / 46.875
known_db = np.array([-5., -3., 2., 4., 6.])
known_gain = 10 ** (np.interp(np.log2(orders), np.log2(centers), known_db) / 20)
amp = .03 / (1 + (orders / 12) ** 1.3)
phase = .2 * np.sin(orders)
complex_amp = amp[:, None] * np.exp(1j * np.column_stack((phase, phase + .4 * np.sin(orders * .3))))
complex_amp[:, 1] *= .8 + .1 * np.sin(orders)
# Separate resolved-carrier positive control; tracker parameters are unchanged.
complex_amp[[2, 4, 6]] *= np.array([3., 6., 2.])[:, None]


def source(rows, gain):
    times = np.array([r['seconds'] for r in rows])
    roots = np.array([r['root_hz'] for r in rows])
    start = np.floor((times[0] - .2) * 48000) / 48000
    t = start + np.arange(int(np.ceil((times[-1] + .2 - start) * 48000))) / 48000
    hz = np.interp(t, times, roots)
    cycle = np.r_[0., np.cumsum((hz[1:] + hz[:-1]) / 96000)]
    audio = np.zeros((len(t), 2))
    for h in range(288):
        audio += np.real(np.exp(2j * np.pi * (h + 1) * cycle)[:, None] * complex_amp[h] * gain[h])
    return audio, start, times, roots


def measure(audio, start, times, roots, rising):
    _, _, evidence, z = describe(audio, start, times, roots, times[0], times[-1])
    keep = select_windows(evidence, rising)
    if not keep.any():
        raise ValueError('Known sweep produced no selected window')
    return np.mean(abs(z[keep]) ** 2, axis=0), int(keep.sum())


report = dict(schema='vsl.state-colour-controls/1', pairs=[], tracked_clock=[],
              scope='Resolved reference-carrier stereo OSC sweeps; dense-carrier tracking failure retained in controls_attempt1; not recording validation')
means = {}
for pair in (1, 2, 4):
    for kind in ('rise', 'fall'):
        name = kind + str(pair)
        rows = clocks['cases'][name]['5']['rows']
        audio, start, times, roots = source(rows, np.ones(288))
        means[name], count = measure(audio, start, times, roots, kind == 'rise')
        s = observe(audio, start, 80, hop=240)
        track = follow(s['hz'], s['seconds'], s['power_low'], times[0], times[-1], roots[0], 5)
        row = dict(case=name, status=track['status'], selected=count)
        if track['rows']:
            observed = np.array([r['root_hz'] for r in track['rows']])
            at = np.array([r['seconds'] for r in track['rows']])
            row['root_rms_error_hz'] = float(np.sqrt(np.mean((observed - np.interp(at, times, roots)) ** 2)))
            try:
                power, _ = measure(audio, start, at, observed, kind == 'rise')
                row['power'] = power.tolist()
            except ValueError as exc:
                row['measurement_error'] = str(exc)
        report['tracked_clock'].append(row)
        if kind == 'rise':
            changed, _, _, _ = source(rows, known_gain)
            means[name + '_known'], _ = measure(changed, start, times, roots, True)
    flat = shape_delta(means['fall' + str(pair)], means['rise' + str(pair)]).mean(axis=1)
    measured = shape_delta(means['fall' + str(pair)], means['rise' + str(pair) + '_known']).mean(axis=1)
    ideal = shape_delta(abs(complex_amp) ** 2, abs(complex_amp * known_gain[:, None]) ** 2).mean(axis=1)
    row = dict(pair=pair, zero_shape_error_db=flat.tolist(), known_shape_error_db=(measured - ideal).tolist())
    tracked = report['tracked_clock'][-2:]
    if all('power' in x for x in tracked):
        delta = shape_delta(np.array(tracked[1].pop('power')), np.array(tracked[0].pop('power'))).mean(axis=1)
        row['tracked_zero_shape_error_db'] = delta.tolist()
    report['pairs'].append(row)
    print('pair', pair, 'zero max', float(max(abs(flat))), 'known max', float(max(abs(measured - ideal))))

# A missing reference with a strong, distant harmonic must remain missing.
t = np.arange(48000) / 48000
missing = np.column_stack((.2 * np.cos(2 * np.pi * 7 * 47 * t), .15 * np.cos(2 * np.pi * 7 * 47 * t + .3)))
s = observe(missing, 0, 80, hop=240)
missing_result = follow(s['hz'], s['seconds'], s['power_low'], .2, .8, 47, 5)
report['missing_reference'] = missing_result['status']
report['maximum_zero_shape_error_db'] = max(max(abs(np.array(x['zero_shape_error_db']))) for x in report['pairs'])
report['maximum_known_shape_error_db'] = max(max(abs(np.array(x['known_shape_error_db']))) for x in report['pairs'])
report['maximum_tracked_zero_shape_error_db'] = max((max(abs(np.array(x['tracked_zero_shape_error_db']))) for x in report['pairs'] if 'tracked_zero_shape_error_db' in x), default=None)
report['result'] = ('pass' if report['maximum_zero_shape_error_db'] < .5 and
                    report['maximum_known_shape_error_db'] < .5 and
                    report['maximum_tracked_zero_shape_error_db'] is not None and
                    report['maximum_tracked_zero_shape_error_db'] < .5 and
                    all('root_rms_error_hz' in x and 'measurement_error' not in x for x in report['tracked_clock']) and
                    not missing_result['rows'] else 'fail')
repo = Path(__file__).resolve().parents[1]
report['source_sha256'] = {p.relative_to(repo).as_posix(): sha(p) for p in
    (Path(__file__), repo / 'tools/state_colour_v2/features.py', repo / 'tools/state_colour_v2/clock.py',
     repo / 'tools/state_dna_v1/compare.py', repo / 'tools/exterior_clock_v1/warp.py',
     repo / 'tools/sound_dna/windowed.py', repo / 'tools/shift_evidence_v1/spectrum.py')}
report['clocks_sha256'] = sha(args.clocks / 'report.json')
(args.out / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
print(json.dumps({k: v for k, v in report.items() if k.startswith('maximum') or k == 'result'}))
sys.exit(report['result'] != 'pass')

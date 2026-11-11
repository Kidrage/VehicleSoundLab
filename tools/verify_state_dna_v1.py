"""Check state-colour measurements against known sweeps and explicit EQ."""
import argparse
import json
from pathlib import Path
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace', type=Path, required=True)
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()
sys.path.insert(0, str(args.workspace/'tools/python_deps'))
import numpy as np
from state_dna_v1.compare import describe, match, difference
from drive_evidence_v1.sources import sha

args.out.mkdir(parents=True, exist_ok=False)
t = np.arange(48000*2)/48000
clock = np.arange(.2, 1.5, .001)
orders = np.arange(1, 161)
amplitude = .006/np.sqrt(orders)
amplitude[[2, 4, 6, 14, 19]] = [.04, .15, .03, .025, .015]
phase = np.random.default_rng(541).uniform(-np.pi, np.pi, len(orders))
reference_hz = orders*46.875
equalizer = np.ones(len(orders))
equalizer[(reference_hz >= 400) & (reference_hz < 1200)] *= 2
equalizer[(reference_hz >= 1200) & (reference_hz < 3000)] *= np.sqrt(2)
controls = {}
for name, stop, first, last, colour in [('fall', 1.0, 54, 32, False),
                                     ('rise_null', .65, 31, 56, False),
                                     ('rise_colour', .65, 31, 56, True),
                                     ('rise_clock_drift', .65, 31, 56, False)]:
    start = .4
    true_hz = np.interp(t, [0, start, stop, t[-1]], [first, first, last, last])
    cycles = np.r_[0, np.cumsum((true_hz[1:]+true_hz[:-1])/(2*48000))]
    source = np.zeros((len(t), 2))
    for k, order in enumerate(orders):
        a = amplitude[k]*(equalizer[k] if colour else 1)
        source[:, 0] += a*np.cos(2*np.pi*order*cycles+phase[k])
        source[:, 1] += .8*a*np.cos(2*np.pi*order*cycles+phase[k]+.35)
    roots = np.interp(clock, t, true_hz)
    # Unknown constant frequency bias emulates a tracker needing phase polish.
    supplied = roots*1.004
    if name == 'rise_clock_drift':
        supplied = roots*(1+.02*np.sin(2*np.pi*2*(clock-.4)))
    _, where, evidence, rows = describe(source, 0, clock, supplied, start, stop)
    matched = match(rows, np.asarray(evidence['window_root_hz']), [(45, 50)])[0]
    assert matched['windows'] >= 3
    controls[name] = dict(evidence=evidence, matched=matched)

a = controls['fall']['matched']['mean_power_LR']
null = difference(a, controls['rise_null']['matched']['mean_power_LR'])
coloured = difference(a, controls['rise_colour']['matched']['mean_power_LR'])
drift = difference(a, controls['rise_clock_drift']['matched']['mean_power_LR'])
# The first five bands have intentional known energy; 8..14k has none in this
# control and is not scored as if a tiny leakage floor were real source energy.
null_error = float(np.max(abs(np.asarray(null['after_minus_before_db_LR'])[:5])))
expected = np.array([0, 0, 20*np.log10(2), 10*np.log10(2), 0])
colour_error = float(np.max(abs(np.asarray(coloured['after_minus_before_db_LR'])[:5]-expected[:, None])))
drift_error = float(np.max(abs(np.asarray(drift['after_minus_before_db_LR'])[:5])))
assert null_error < .5, null_error
assert colour_error < .5, colour_error
assert drift_error < .5, drift_error
report = dict(schema='vsl.state-dna-controls/1', result='pass', null_max_band_error_db=null_error,
    known_colour_max_band_error_db=colour_error, drifting_clock_max_band_error_db=drift_error,
    expected_band_delta_db=expected.tolist(), null=null, known_colour=coloured,
    drifting_clock=drift, controls=controls,
    limits=['Known coherent OSC and constant gain; not a real-source confidence interval',
            'Does not establish real recording clock identity or physical load',
            'Only five populated bands scored; no claim for8..14k'],
    source_sha256={p.relative_to(Path(__file__).resolve().parents[1]).as_posix():sha(p) for p in
        [Path(__file__), *Path(__file__).with_name('state_dna_v1').glob('*.py'),
         Path(__file__).parent/'exterior_clock_v1/warp.py', Path(__file__).parent/'sound_dna/windowed.py']})
(args.out/'verification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(dict(result='pass', null_max_db=null_error, known_colour_max_db=colour_error, drifting_clock_max_db=drift_error)))

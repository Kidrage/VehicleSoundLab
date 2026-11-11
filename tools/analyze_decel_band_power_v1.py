"""Bound phase-free band observations before making any state-colour target."""
import argparse
import json
from pathlib import Path
import shutil
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace', type=Path, required=True)
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()
repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(args.workspace/'tools/python_deps'))
import numpy as np
from drive_evidence_v1.sources import read, sha
from cabin_decel_v1.power import measure
from cabin_decel_v1.fixtures import source
from state_colour_v2.clock import follow
from shift_evidence_v1.spectrum import observe

args.out.mkdir(parents=True, exist_ok=False)
root = args.workspace/'references/analysis/cabin_decel_v1'
input_path = root/'exploration1/report.json'
exploration = json.loads(input_path.read_text(encoding='utf-8'))
audio, provenance = read(args.workspace, 'E_corsa_first_context', 'cabin_dynamic_observation')
assert provenance == exploration['provenance']
cases = []
controls = []
for case in exploration['cases']:
    seconds = case['case']['seconds']
    # Keep original audio samples and the same physical observation interval.
    first = round((seconds[0]-.1-provenance['seconds'][0])*48000)
    stop = round((seconds[1]+.1-provenance['seconds'][0])*48000)
    fragment = audio[first:stop]
    source_start = provenance['seconds'][0]+first/48000
    item = dict(case=case['case'], observations=[])
    for reference, entry in case['references'].items():
        rows = entry['tracking']['rows']
        if not rows:
            continue
        times = np.array([r['seconds'] for r in rows])
        roots = np.array([r['root_hz'] for r in rows])
        for scale in (.98, 1., 1.02):
            obs = measure(fragment, source_start, times, roots, seconds, scale)
            item['observations'].append(dict(reference=int(reference), scale=scale, **obs))
    primary = next(r for r in item['observations'] if r['reference'] == 5 and r['scale'] == 1)
    base = np.array(primary['shape_relative_mid_db_LR'])
    changes = np.array([np.array(r['shape_relative_mid_db_LR'])-base for r in item['observations']])
    item.update(primary_shape_db_LR=base.tolist(),
                sensitivity_min_db_LR=changes.min(axis=0).tolist(),
                sensitivity_max_db_LR=changes.max(axis=0).tolist(),
                maximum_sensitivity_db=float(abs(changes).max()))
    cases.append(item)

    rows = case['references']['5']['tracking']['rows']
    ft = np.array([r['seconds'] for r in rows]);ff = np.array([r['root_hz'] for r in rows])
    at = np.arange(57600)/48000
    fixtures = [source(at, ft-ft[0]+.2, ff, changed) for changed in (False, True)]
    bands = []
    for changed, (fixture, truth) in zip((False, True), fixtures):
        observed = observe(fixture, 0, 80)
        track = follow(observed['hz'], observed['seconds'], observed['power_low'],
                       .2, .995, float(np.interp(.2, at, truth)), 5)
        if not track['rows']:
            raise ValueError('Known positive control lost its observed reference')
        t = np.array([r['seconds'] for r in track['rows']])
        f = np.array([r['root_hz'] for r in track['rows']])
        measured = measure(fixture, 0, t, f, [.2, .995])
        bands.append(np.array(measured['shape_relative_mid_db_LR']))
    expected = np.array([-3.010299956639812, -6.020599913279624])[:, None]
    error = bands[1]-bands[0]-expected
    controls.append(dict(case=case['case']['id'], expected_change_db=expected[:, 0].tolist(),
                         measured_change_db_LR=(bands[1]-bands[0]).tolist(),
                         max_error_db=float(abs(error).max())))
    print(case['case']['id'], 'raw band sensitivity', round(item['maximum_sensitivity_db'], 3),
          'known-colour error', round(float(abs(error).max()), 4), flush=True)

maximum = max(r['max_error_db'] for r in controls)
result = dict(schema='vsl.cabin-deceleration-raw-band/1', provenance=provenance,
              input_sha256=sha(input_path), cases=cases, known_controls=controls,
              maximum_control_error_db=maximum, known_control_passed=maximum < .5,
              source_phase_warp=False, runtime_changes=False, state_target_promoted=False,
              limits=['Wide-band power only; no narrow harmonic amplitude/phase inference',
                      'Reference variants and+/-2% scales are sensitivity probes, not uncertainty intervals',
                      'One deceleration with changing speed/root; no independent load or pedal evidence',
                      'Band robustness does not establish complete state-colour or naturalness'])
paths = [Path(__file__), repo/'tools/cabin_decel_v1/power.py', repo/'tools/cabin_decel_v1/fixtures.py',
         repo/'tools/drive_evidence_v1/sources.py', repo/'tools/state_colour_v2/clock.py',
         repo/'tools/shift_evidence_v1/spectrum.py']
result['source_sha256'] = {p.relative_to(repo).as_posix(): sha(p) for p in paths}
for p in paths:
    target = args.out/'exact_sources'/p.relative_to(repo)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(p, target)
(args.out/'report.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n',
                                   encoding='utf-8', newline='\n')

"""Observe fixed third-gear deceleration windows using separate FFT carriers."""
import argparse
import json
from pathlib import Path
import shutil
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace', type=Path, required=True)
parser.add_argument('--out', type=Path, required=True)
parser.add_argument('--method', choices=('two', 'four'), default='two')
parser.add_argument('--plan', type=Path)
args = parser.parse_args()
repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(args.workspace / 'tools/python_deps'))
import numpy as np
import soundfile as sf
from drive_evidence_v1.sources import read, sha
from shift_evidence_v1.spectrum import observe
from state_colour_v2.clock import follow
from state_dna_v1.compare import describe, difference
from phase_clock_v1.projection import polish as short_polish, diagnostics, independent_agreement
from exterior_clock_v1.warp import polish as long_polish

def polish(*parameters):
    if args.method == 'two':
        return short_polish(*parameters)
    normalized, positions, evidence = long_polish(*parameters)
    measured = diagnostics(normalized, parameters[4])
    evidence['diagnostics'] = measured
    evidence['independent_agreement'] = independent_agreement(measured)
    return normalized, positions, evidence

plan_path = (args.plan or repo / 'research/cabin_decel_v1_plan.json').resolve()
plan = json.loads(plan_path.read_text(encoding='utf-8'))
args.out.mkdir(parents=True, exist_ok=False)
sources = [Path(__file__), plan_path, repo/'tools/drive_evidence_v1/sources.py',
           repo/'tools/shift_evidence_v1/spectrum.py', repo/'tools/state_colour_v2/clock.py',
           repo/'tools/state_dna_v1/compare.py', repo/'tools/phase_clock_v1/projection.py',
           repo/'tools/exterior_clock_v1/warp.py', repo/'tools/sound_dna/windowed.py']
hashes = {p.relative_to(repo).as_posix(): sha(p) for p in sources}
for path in sources:
    target = args.out / 'exact_sources' / path.relative_to(repo)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, target)

audio, provenance = read(args.workspace, plan['source_segment'], plan['source_use'])
observation = observe(audio, provenance['seconds'][0], 80)
report = dict(schema='vsl.cabin-deceleration-exploration/1', plan_sha256=sha(plan_path),
              method=args.method,
              provenance=provenance, cases=[], source_sha256=hashes, runtime_changes=False,
              limits=['All clocks use one FFT observation and the same recording',
                      'Local carrier agreement is not a physical RPM/load/fuel measurement',
                      'Generic two-cycle refiner has not passed full prior qualification',
                      'Fixed windows are one deceleration event, not independent repeated trials'])

for case in plan['cases']:
    directory = args.out / case['id']
    directory.mkdir()
    result = dict(case=case, references={}, comparisons=[])
    values = {}
    for reference in [plan['primary_reference'], *plan['comparison_references']]:
        item = dict(reference=reference)
        track = follow(observation['hz'], observation['seconds'], observation['power_low'],
                       *case['seconds'], case['initial_root_hz'], reference)
        item['tracking'] = track
        if not track['rows']:
            item['status'] = 'missing_coarse_path'
            result['references'][str(reference)] = item
            continue
        times = np.array([r['seconds'] for r in track['rows']])
        roots = np.array([r['root_hz'] for r in track['rows']])
        try:
            # Roundoff-safe bounds only; never extend beyond observed points.
            start = max(case['seconds'][0], float(times[0]))
            stop = min(case['seconds'][1], float(times[-1]))
            normalized, positions, evidence, z = describe(
                audio, provenance['seconds'][0], times, roots, start, stop,
                reference=reference, phase_refiner=polish)
        except ValueError as exc:
            item.update(status='phase_rejected', reason=str(exc))
            result['references'][str(reference)] = item
            continue
        item.update(status='measured', evidence=evidence)
        values[reference] = (positions, z, evidence)
        sf.write(directory/f'reference{reference}_normalized.wav', normalized, 48000, subtype='FLOAT')
        np.savez_compressed(directory/f'reference{reference}_coordinates.npz',
                            source_seconds=positions, complex_rows=z)
        result['references'][str(reference)] = item
    primary = plan['primary_reference']
    if primary in values:
        positions, z, evidence = values[primary]
        main_times = np.array(evidence['window_source_seconds'])
        main_roots = np.array(evidence['window_root_hz'])
        for reference in plan['comparison_references']:
            if reference not in values:
                continue
            other = values[reference][2]
            other_times = np.array(other['window_source_seconds'])
            other_roots = np.array(other['window_root_hz'])
            keep = (main_times >= other_times[0]) & (main_times <= other_times[-1])
            error = abs(main_roots[keep] - np.interp(main_times[keep], other_times, other_roots)) / main_roots[keep]
            delta = difference(evidence['harmonic_mean_power_LR'], other['harmonic_mean_power_LR'])
            # The two lowest bands may contain few harmonics. Qualify the DNA
            # mid/high region400..8000Hz; report all bands including the rest.
            shape = np.array(delta['shape_after_scalar_removal_db_LR'])[2:5]
            result['comparisons'].append(dict(reference=reference,
                relative_root_p95=float(np.percentile(error, 95)),
                relative_root_max=float(error.max()), difference=delta,
                maximum_400_8000_shape_db=float(abs(shape).max())))
        gates = plan['diagnostic_gates']
        passing = [r for r in result['comparisons'] if
                   r['relative_root_p95'] <= gates['maximum_root_relative_p95'] and
                   r['maximum_400_8000_shape_db'] <= gates['maximum_shape_difference_db']]
        result['local_diagnostic_gate'] = bool(
            evidence['correction']['independent_agreement']['passed'] and
            evidence['nonoverlapping_four_cycle_window_upper_bound'] >= gates['minimum_nonoverlapping_four_cycle_windows'] and
            len(passing) >= gates['minimum_comparison_references'])
    else:
        result['local_diagnostic_gate'] = False
    report['cases'].append(result)
    print(case['id'], {k: v['status'] for k, v in result['references'].items()},
          'local gate', result['local_diagnostic_gate'],
          'comparison', [(r['reference'], round(r['relative_root_p95'], 4),
                          round(r['maximum_400_8000_shape_db'], 3)) for r in result['comparisons']], flush=True)

(args.out/'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n',
                                   encoding='utf-8', newline='\n')

"""Analytic projection-leakage evidence; does not read any vehicle audio."""
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
from drive_evidence_v1.sources import sha
from period_structure_v1.phase import observe
from period_structure_v1.fixtures import cases
from period_structure_v1.spectrum import observe as spectrum

args.out.mkdir(parents=True, exist_ok=False)
report = dict(schema='vsl.period-leakage-diagnostic/1', result='running', sources={}, cases=[], source_audio_read=False)
try:
    plan_path = repo/'research/period_structure_v1_leakage_plan.json'
    plan = json.loads(plan_path.read_text(encoding='utf-8'))
    original = json.loads((repo/'research/period_structure_v1_plan.json').read_text(encoding='utf-8'))
    for source in [Path(__file__), plan_path, repo/'research/period_structure_v1_plan.json',
                   repo/'tools/drive_evidence_v1/sources.py', repo/'tools/period_structure_v1/phase.py',
                   repo/'tools/period_structure_v1/spectrum.py',
                   repo/'tools/period_structure_v1/fixtures.py']:
        relative = source.relative_to(repo)
        target = args.out/'exact_sources'/relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        report['sources'][relative.as_posix()] = sha(source)
    fixtures, _ = cases(plan['cycle_samples'], plan['coarse_root_hz'])
    for case in fixtures:
        if case['id'] not in plan['cases']:
            continue
        row = dict(id=case['id'], windows={})
        for cycles in plan['projection_cycles']:
            parameters = dict(original['phase'], projection_cycles=cycles)
            observed = observe(case['audio'], plan['cycle_samples'], parameters)
            maximum = max(pair['worst_p95_relative_drift_cycles'] for pair in observed['pairs'])
            row['windows'][str(cycles)] = dict(maximum_pair_drift_cycles=maximum, pairs=observed)
        row['long_window_passed'] = row['windows']['20']['maximum_pair_drift_cycles'] <= plan['rules']['maximum_long_window_pair_drift_cycles']
        report['cases'].append(row)
    assert len(report['cases']) == len(plan['cases'])
    assert all(row['long_window_passed'] for row in report['cases'])
    am = next(row for row in report['cases'] if row['id'] == 'am_sidebands')
    assert am['windows']['4']['maximum_pair_drift_cycles'] >= plan['rules']['minimum_short_window_AM_pair_drift_cycles']
    null = plan['warp_null']
    coordinate_file = args.workspace/null['coordinate_file']
    with np.load(coordinate_file, allow_pickle=False) as archive:
        positions = archive['source_seconds']
    base = float(np.median(1/(plan['cycle_samples']*np.diff(positions))))
    source_time = np.arange(round((positions[-1]-positions[0])*48000))/48000+positions[0]
    nulls = {}
    for name, time, samples_per_cycle in [('original_constant_integer', source_time, 48000/base),
                                        ('saved_warp_constant_integer', positions, plan['cycle_samples'])]:
        audio = np.column_stack([sum(amp*np.sin(2*np.pi*order*base*(time-positions[0]-delay)+phase)
            for order, amp, phase in zip(null['orders'], null['amplitudes'], null['phases_radians']))
            for delay in (0., null['right_delay_seconds'])])
        split = len(audio)//2
        nulls[name] = {part: spectrum(part_audio, samples_per_cycle, base, original['spectrum'])[0]
            for part, part_audio in [('full', audio), ('first_half', audio[:split]), ('last_half', audio[split:])]}
    assert all(channel['lattice']['fractional_peaks']==0
        for item in nulls['original_constant_integer'].values() for channel in item['channels'])
    report['warp_null'] = dict(coordinate_file=null['coordinate_file'], coordinate_file_sha256=sha(coordinate_file),
        members_read=['source_seconds'], observation=nulls,
        processing='Evaluate exact analytic constant-Hz carriers at saved source times; no PCM, FIR or interpolation errors added',
        interpretation='Null measures coordinate-induced spreading only. It does not estimate the unknown true vehicle clock or remove genuine fractional source lines.')
    report.update(result='analytic_short_projection_leakage_confirmed',
        conclusion='Known perfectly common carrier phase can appear inconsistent in four-coarse-cycle projections when nearby fifth-grid lines leak into them; source causality remains unproven',
        runtime_changed=False, model_exported=False, original_real_phase_gate='rejected_unchanged')
    print(json.dumps(dict(result=report['result'], cases=[dict(id=row['id'], drift={key:item['maximum_pair_drift_cycles'] for key,item in row['windows'].items()}) for row in report['cases']])), flush=True)
except Exception as exc:
    report.update(result='failed', error=repr(exc))
    raise
finally:
    (args.out/'report.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n', encoding='utf-8')

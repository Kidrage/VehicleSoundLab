"""Qualify measured consensus and stereo warp against independent analytic truth."""
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
from shift_evidence_v1.spectrum import observe
from exterior_clock_v1.warp import warp, render_positions
from stationary_dna_v1.measure import moments, difference
from multicarrier_clock_v1.coarse import track
from multicarrier_clock_v1.phase import refine
from multicarrier_clock_v1.fixtures import make

args.out.mkdir(parents=True, exist_ok=False)
report = dict(schema='vsl.multicarrier-clock-validation/1', result='running', cases=[], sources={}, real_source_evaluated=False)
try:
    plan_path = repo/'research/multicarrier_clock_v1_plan.json'
    plan = json.loads(plan_path.read_text(encoding='utf-8'))
    sources = [Path(__file__), plan_path, repo/'tools/drive_evidence_v1/sources.py',
               repo/'tools/shift_evidence_v1/spectrum.py', repo/'tools/state_colour_v2/clock.py',
               repo/'tools/exterior_clock_v1/warp.py', repo/'tools/phase_clock_v1/projection.py',
               repo/'tools/startup_catch_v1/clock.py', repo/'tools/stationary_dna_v1/measure.py',
               repo/'tools/sound_dna/windowed.py']
    sources += list((repo/'tools/multicarrier_clock_v1').glob('*.py'))
    for source in sources:
        relative = source.relative_to(repo)
        target = args.out/'exact_sources'/relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        report['sources'][relative.as_posix()] = sha(source)
    report['plan_sha256'] = sha(plan_path)
    for case in plan['fixtures']:
        item = dict(case=case, status='running', supports_profile=False)
        audio, times, true_phase, true_frequency = make(case, plan['seconds'])
        observed = observe(audio, 0, plan['coarse']['window_ms'], hop=plan['coarse']['hop_samples'])
        path = track(observed, *plan['selected_seconds'], case['root_hz'], plan['coarse'])
        item['track_status'] = path['status']
        directory = args.out/case['id']
        directory.mkdir()
        (directory/'coarse.json').write_text(json.dumps(path, indent=2)+'\n', encoding='utf-8')
        if path['rows']:
            x = np.array([v['seconds'] for v in path['rows']])
            hz = np.array([v['root_hz'] for v in path['rows']])
            truth = np.interp(x, times, true_frequency)
            item['coarse_relative_root_p95'] = float(np.percentile(abs(hz-truth)/truth, 95))
            try:
                first, where, initial = warp(audio, 0, x, hz, *plan['selected_seconds'])
                normalized, where, phase_info = refine(audio, 0, first, where,
                                                       initial['source_cutoff_hz'], plan['phase'])
                inferred = 1/(1024*np.diff(where))
                truth = np.interp((where[1:]+where[:-1])/2, times, true_frequency)
                root_error = float(np.percentile(abs(inferred-truth)/truth, 95))
                origin = float(np.interp(where[0], times, true_phase))
                oracle_where = np.interp(origin+np.arange(len(where))/1024, true_phase, times)
                oracle = render_positions(audio, 0, oracle_where, phase_info['source_cutoff_hz'])
                delta = difference(moments(oracle, case['root_hz'], plan['harmonics'], plan['bands_hz']),
                                   moments(normalized, case['root_hz'], plan['harmonics'], plan['bands_hz']))
                power_error = float(abs(np.asarray(delta['power_difference_db_LR'])).max())
                correlation_error = float(max(delta['complex_correlation_difference']))
                rules = plan['rules']
                item.update(status='measured', phase=phase_info, root_relative_p95=root_error,
                    maximum_oracle_band_power_error_db=power_error,
                    maximum_oracle_complex_correlation_error=correlation_error, oracle_delta=delta)
                item['supports_profile'] = bool(phase_info['independent_agreement']['passed'] and
                    root_error <= rules['maximum_root_relative_p95'] and
                    power_error <= rules['maximum_oracle_band_power_error_db'] and
                    correlation_error <= rules['maximum_oracle_complex_correlation_error'])
                np.savez_compressed(directory/'coordinates.npz', source_seconds=where)
            except ValueError as exc:
                item.update(status='phase_rejected', reason=str(exc))
        else:
            item['status'] = 'coarse_rejected'
        item['passed'] = (not item['supports_profile']) if case.get('negative') else item['supports_profile']
        report['cases'].append(item)
        (directory/'report.json').write_text(json.dumps(item, indent=2)+'\n', encoding='utf-8')
        print(json.dumps(dict(id=case['id'], status=item['status'], passed=item['passed'],
            supports_profile=item['supports_profile'], root_error=item.get('root_relative_p95'),
            power_error_db=item.get('maximum_oracle_band_power_error_db'), reason=item.get('reason'))), flush=True)
    report.update(result='passed' if all(item['passed'] for item in report['cases']) else 'rejected',
                  model_exported=False, runtime_modified=False, accepted_models_modified=False)
except Exception as exc:
    report.update(result='failed', error=repr(exc))
    raise
finally:
    (args.out/'report.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')

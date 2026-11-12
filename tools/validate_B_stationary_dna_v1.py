"""Validate the unchanged stationary extractor before permitting profile fitting."""
import argparse
import json
from pathlib import Path
import shutil
import sys

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
a = p.parse_args()
repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(a.workspace/'tools/python_deps'))
import numpy as np
from drive_evidence_v1.sources import sha
from exterior_clock_v1.warp import warp, render_positions
from phase_clock_v1.projection import polish, independent_agreement
from shift_evidence_v1.spectrum import observe
from state_colour_v2.clock import follow
from startup_catch_v1.clock import diagnostics
from stationary_dna_v1.fixtures import make
from stationary_dna_v1.measure import moments, difference

a.out.mkdir(parents=True, exist_ok=False)
plan_path = repo/'research/B_stationary_dna_v1_validation_plan.json'
plan = json.loads(plan_path.read_text(encoding='utf-8'))
r = dict(schema='vsl.stationary-dna-validation/1', result='running', cases=[], model_exported=False, sources={})
try:
    sources = [Path(__file__),plan_path,repo/'research/B_stationary_dna_v1_plan.json']
    for package in ('stationary_dna_v1','sound_dna','exterior_clock_v1','phase_clock_v1',
                    'state_colour_v2','shift_evidence_v1','startup_catch_v1'):
        sources += list((repo/'tools'/package).glob('*.py'))
    for source in sources:
        relative = source.relative_to(repo)
        target = a.out/'exact_sources'/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,target)
        r['sources'][relative.as_posix()] = sha(source)
    for case in plan['references']:
        root, reference = case['root_hz'], case['reference']
        for kind in plan['positive_controls']+plan['negative_controls']:
            item = dict(root_hz=root, reference=reference, kind=kind, status='running')
            audio, t, phase = make(root, reference, kind, plan['seconds'])
            observed = observe(audio, 0, 80)
            track = follow(observed['hz'],observed['seconds'],observed['power_low'],
                           *plan['selected_seconds'],root,reference)
            positive = kind in plan['positive_controls']
            item.update(positive_control=positive,track_status=track['status'])
            if track['rows']:
                times = np.array([v['seconds'] for v in track['rows']])
                roots = np.array([v['root_hz'] for v in track['rows']])
                try:
                    first, where, initial = warp(audio,0,times,roots,*plan['selected_seconds'])
                    normalized, where, correction = polish(audio,0,first,where,reference,initial['source_cutoff_hz'])
                    independent = independent_agreement(diagnostics(normalized,reference))
                    item['independent'] = independent
                    inferred = 1/(1024*np.diff(where))
                    truth = np.interp((where[1:]+where[:-1])/2,t,np.gradient(phase)*48000)
                    error = abs(inferred-truth)/truth
                    # Oracle phase uses the analytic fixture; its origin can
                    # differ from the fitted carrier, which does not affect power.
                    origin = float(np.interp(where[0],t,phase))
                    target_phase = origin+np.arange(len(where))/1024
                    oracle_where = np.interp(target_phase,phase,t)
                    oracle = render_positions(audio,0,oracle_where,correction['source_cutoff_hz'])
                    delta = difference(moments(oracle,root,plan['harmonics'],plan['bands_hz']),
                                       moments(normalized,root,plan['harmonics'],plan['bands_hz']))
                    maximum = float(abs(np.array(delta['power_difference_db_LR'])).max())
                    item.update(status='measured',root_relative_p95=float(np.percentile(error,95)),
                                oracle_delta=delta,maximum_oracle_band_power_error_db=maximum,
                                correction=correction)
                    item['supports_profile'] = bool(independent['passed'] and
                        item['root_relative_p95']<=plan['rules']['maximum_root_relative_p95'] and
                        maximum<=plan['rules']['maximum_oracle_band_power_error_db'])
                except ValueError as exc:
                    item.update(status='phase_rejected',reason=str(exc),supports_profile=False)
            else:
                item.update(status='coarse_rejected',supports_profile=False)
            item['passed'] = item['supports_profile'] if positive else not item['supports_profile']
            r['cases'].append(item)
            print(json.dumps({k:item[k] for k in ('root_hz','reference','kind','status','passed','supports_profile')}
                             | {k:item[k] for k in ('root_relative_p95','maximum_oracle_band_power_error_db') if k in item}),flush=True)
    r.update(result='passed' if all(v['passed'] for v in r['cases']) else 'rejected',
             generic_phase_qualification='not_passed_unchanged',original_local_gates=False,
             plan_sha256=sha(plan_path),runtime_modified=False)
except Exception as exc:
    r.update(result='failed',error=repr(exc))
    raise
finally:
    (a.out/'report.json').write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8')

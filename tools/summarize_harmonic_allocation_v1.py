"""Bind all executed attempts and the limited conclusions of allocation V1."""
import argparse
import json
from pathlib import Path
import sys

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True)
args=parser.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
from drive_evidence_v1.sources import sha

root=args.workspace/'references/analysis/harmonic_allocation_v1'
attempts=[]
for folder in ('analysis1','analysis2','analysis3'):
    report=json.loads((root/folder/'report.json').read_text(encoding='utf-8'))
    for name,digest in report['source_sha256'].items():
        assert sha(root/folder/'exact_sources'/name)==digest,(folder,name)
    for name,digest in report['input_sha256'].items():assert sha(name)==digest,name
    for ob in report['observations']:
        assert sha(root/folder/(ob['name']+'.npz'))==ob['arrays_sha256']
    attempts.append(dict(folder=folder,result=report['result'],error=report.get('error'),
                         report_sha256=sha(root/folder/'report.json')))
assert attempts[0]['result']=='failed'
r=json.loads((root/'analysis3/report.json').read_text(encoding='utf-8'))
assert r['result']=='diagnostics_completed' and not r['shape_extraction_qualified']
assert not r['runtime_changes'] and not r['new_fit'] and r['accepted_models_unchanged']
for name,digest in r['source_sha256'].items():assert sha(repo/name)==digest,name

def rows(name):return next(ob['configurations'] for ob in r['observations'] if ob['name']==name)
def extent(items):return [min(items),max(items)]
target=next(ob for ob in r['observations'] if ob['name']=='fixed_A_reference')
generated=[ob for ob in r['observations'] if ob['name'].startswith('accepted_DNA_LF_')]
noise=[ob for ob in r['observations'] if ob['name'].startswith('known_stationary_noise_')]
gates=[dict(name=ob['name'],window=row['window'],origin_frame=row['origin_frame'],**row[key])
    for ob in r['observations'] for row in ob['configurations']
    for key in ('common_gain_shape_gate','known_shape_AM_gate') if key in row]
stereo=r['stereo_scope'].copy()
for key,value in list(stereo.items()):
    if key.endswith('_relative_rms'):stereo[key+'_db']=float(20*np.log10(max(value,1e-30)))
sources=[Path(__file__),repo/'tools/freeze_harmonic_allocation_v1.py',repo/'tools/analyze_harmonic_allocation_v1.py',
         repo/'research/harmonic_allocation_v1_plan.json',*sorted((repo/'tools/harmonic_allocation_v1').glob('*.py'))]
summary=dict(schema='vsl.harmonic-allocation-summary/1',date='2026-11-12',result='diagnostics_only',
    evidence_root=str(root),base_commit=r['base_commit'],attempts=attempts,
    observations=len(r['observations']),window_configurations=sum(len(ob['configurations']) for ob in r['observations']),
    fraction_controls=len(r['fraction_controls']),
    known_fraction=dict(nominal_range=extent([row['nominal_fraction'] for row in r['fraction_controls']]),
        known_clock_corrected_minimum=min(row['known_clock_corrected_fraction'] for row in r['fraction_controls']),
        analytic_fraction_maximum_error=max(row['analytic_fraction_error'] for row in r['fraction_controls'])),
    slow_shape=dict(target_rms_db_range=extent([v for row in target['configurations'] for v in row['slow_shape_rms_db_LR']]),
        target_cross_window_correlation_range=extent([v for row in target['cross_window_shape'] for pair in row['comparisons'] for v in pair['correlation_LR']]),
        frozen_C_rms_db_range=extent([v for ob in generated for row in ob['configurations'] for v in row['slow_shape_rms_db_LR']]),
        stationary_noise_rms_db_range=extent([v for ob in noise for row in ob['configurations'] for v in row['slow_shape_rms_db_LR']]),
        stationary_noise_cross_window_correlation_range=extent([v for ob in noise for row in ob['cross_window_shape'] for pair in row['comparisons'] for v in pair['correlation_LR']]),
        meaning='Descriptive short-block readouts, not physical source AM or independent trials'),
    controls=dict(maximum_direct_DFT_relative_error=max(row['direct_DFT_relative_error'] for ob in r['observations'] for row in ob['configurations']),
        maximum_projection_relative_error=max(row['projection_relative_error'] for ob in r['observations'] for row in ob['configurations']),
        maximum_shape_AM_error_db=max(row.get('known_shape_AM_error_db',0) for ob in r['observations'] for row in ob['configurations']),
        shape_extraction_qualified=r['shape_extraction_qualified'],failed_original_gates=[row for row in gates if not row['passed']]),
    actual_C_power_budget=r['actual_C_power_budget'],stereo_scope=stereo,
    allocation_decision=r['allocation_decision'],
    c_h_count=r['c_h_count'],c_index_sha256=r['c_index_sha256'],accepted_models_unchanged=True,
    runtime_changes=False,models_changed=False,state_mapping_changed=False,human_accepted=False,
    current_source_sha256={p.relative_to(repo).as_posix():sha(p) for p in sources},
    evidence_sha256={p.relative_to(root).as_posix():sha(p) for p in sorted(root.rglob('*')) if p.is_file() and '__pycache__' not in p.parts},
    input_sha256=r['input_sha256'],limits=r['limits']+[
        'First early-stop failure and all completed attempts retain the same plan thresholds; four rect1 common-gain shape gates remain failed',
        'Common-gain total shape leakage is 0.024..0.027dB while its slow readout is under0.010dB; this small counterexample does not erase the real-A1dB observation',
        'The raw A master is already nearly dual-mono in this interval; the normalized target cannot validate stereo width',
        'Next distinguish local line concentration from clock drift before any bounded DNA/cloud redistribution; use separate stereo recordings for width'])
assert sha(repo/'handoff/C文件索引.csv')==summary['c_index_sha256']
(repo/'research/harmonic_allocation_v1_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(result=summary['result'],shape=summary['slow_shape'],stereo=stereo,
    failed_gates=len(summary['controls']['failed_original_gates']))),flush=True)

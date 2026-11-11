"""Summarize successful diagnostics and an explicitly unqualified AR8 candidate."""
import argparse
import csv
import json
from pathlib import Path
import subprocess
import sys

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True)
args=parser.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
from drive_evidence_v1.sources import sha

root=args.workspace/'references/analysis/magnitude_timescale_v1'
names=('analysis1','verification1','factor8_1','factor8_verification1','factor8_verification2')
reports={name:json.loads((root/name/'report.json').read_text(encoding='utf-8')) for name in names}
a,v,f,failed,checked=(reports[n] for n in names)
assert a['result']==v['result']==f['result']=='pass'
assert failed['result']=='failed' and checked['result']=='not_passed' and checked['all_checks_executed']
assert v['analysis_report_sha256']==f['timescale_report_sha256']==sha(root/'analysis1/report.json')
assert failed['candidate_report_sha256']==checked['candidate_report_sha256']==sha(root/'factor8_1/report.json')
for name,result in reports.items():
    for source,digest in result['source_sha256'].items():assert sha(root/name/'exact_sources'/source)==digest,(name,source)
for name,digest in a['input_sha256'].items():assert sha(name)==digest,name
for row in a['clock_controls']:assert sha(root/'analysis1'/row['file'])==row['sha256']
for result,folder in ((a,'analysis1'),(f,'factor8_1')):
    for row in result['trials']:assert sha(root/folder/row['path'])==row['sha256']
assert all(row['float_samples_equal'] for row in v['trials'])
with (repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig',newline='') as stream:index=list(csv.DictReader(stream))
assert len(index)==436
for row in index:assert sha(repo/row['文件'])==row['SHA-256'],row['文件']
accepted=json.loads((repo/'research/coherent_low_v1_acceptance.json').read_text(encoding='utf-8'))
assert sha(repo/accepted['model'])==accepted['model_sha256']
assert sha(repo/'voices/dna_bank_v1/V10 Exterior.model')==accepted['dna_model_sha256']

trials=[]
ref_power=np.array(f['reference']['mean_band_power_LR'])
for old,new in zip(a['trials'],f['trials']):
    assert old['seed']==new['seed']
    trials.append(dict(seed=new['seed'],old_medians=old['old']['summary'][0]['medians'],
        AR8_medians=new['measurement']['summary'][0]['medians'],peak=new['peak'],
        AR8_mean_band_power_error_db_LR=(10*np.log10(np.array(new['measurement']['mean_band_power_LR'])/ref_power)).tolist()))
sources=[Path(__file__),repo/'tools/freeze_magnitude_timescale_v1.py',
    repo/'tools/analyze_magnitude_timescale_v1.py',repo/'tools/verify_magnitude_timescale_v1.py',
    repo/'tools/explore_factor_ar8_v1.py',repo/'tools/verify_factor_ar8_v1.py',
    repo/'research/magnitude_timescale_v1_plan.json',repo/'research/factor_ar8_v1_plan.json',
    *sorted((repo/'tools/magnitude_timescale_v1').glob('*.py'))]
summary=dict(schema='vsl.magnitude-timescale-summary/1',date='2026-11-12',
    result='diagnostics_pass_candidate_not_qualified',evidence_root=str(root),
    base_commit=a['base_commit'],stages={name:dict(result=r['result'],report_sha256=sha(root/name/'report.json')) for name,r in reports.items()},
    cap=dict(decay_seconds=a['cap_decay_seconds'],recovery_max_error=a['statistics']['old_rho_recovery_max_error'],
        factor_variance_fraction_above_old_cap=a['statistics']['factor_variance_fraction_above_old_cap'],
        residual_variance_fraction_above_old_cap=a['statistics']['residual_variance_fraction_above_old_cap'],
        factor_rho_range=[min(a['statistics']['raw_factor_rho']),max(a['statistics']['raw_factor_rho'])],
        residual_rho_range=[min(a['statistics']['raw_residual_rho']),max(a['statistics']['raw_residual_rho'])],
        audio_comparison=v['trials'],decision='Cap increase changes no decoded FLOAT sample; not a fix'),
    clock_controls=[dict(relative_error=r['clock_fractional_error'],
        magnitude_rms_error_db_LR=r['harmonic_magnitude_rms_error_db_LR'],
        high_magnitude_rms_error_db_LR=r['high_harmonic_magnitude_rms_error_db_LR'],
        exact_clock_waveform_relative_error=r.get('waveform_relative_error'),
        slow_shape_rms_db_LR=r['band_observations']['summary'][0]['medians']['slow_shape_rms_db_LR']) for r in a['clock_controls']],
    independent_detuned_tone_controls=v['detuned_tone_controls'],
    maximum_actual_clock_DFT_error=max(r['maximum_complex_relative_error'] for r in v['actual_clock_dft']),
    factor_lag_observations=v['factor_lag_observations'],
    candidate=dict(order=8,factors=f['factors'],AR1_render_parity_max_error=f['AR1_render_parity_max_error'],
        stationary_covariance_max_error=f['stationary_covariance_max_error'],known_state_controls=f['controls'],
        trials=trials,reference_medians=f['reference']['summary'][0]['medians'],
        initial_verification_error=failed['error'],qualification='not_passed',
        verification=checked,decision='Retain offline only; no new listening page or replacement of the existing pending review'),
    c_h_count=len(index),c_index_sha256=sha(repo/'handoff/C文件索引.csv'),
    accepted_models_unchanged=True,runtime_changes=False,model_bank_changes=False,new_state_mapping=False,human_accepted=False,
    current_source_sha256={p.relative_to(repo).as_posix():sha(p) for p in sources},
    evidence_sha256={p.relative_to(root).as_posix():sha(p) for p in sorted(root.rglob('*'))
        if p.is_file() and '__pycache__' not in p.parts},
    input_sha256=a['input_sha256'],limits=a['limits']+f['limits']+checked['limits']+[
        'The synthetic clock controls do not identify the real error or explain all reference envelope differences',
        'Finite block lag ratios and ideal population AR1 powers are descriptive comparisons, not independent significance tests',
        'Some WAV file headers differ although decoded FLOAT samples are exact in the cap comparison',
        'Historical phase minimum_power_relative_to_loudest_window_LR field is an amplitude ratio; no power inference uses it',
        'The first AR8 verifier stopped on its second seed; verification2 preserves thresholds and completes all checks while retaining not_passed',
        'Existing harmonic magnitude V1 listening remains pending; no duplicate feedback question, C test rerun, device or 7.1.4 acceptance'])
(repo/'research/magnitude_timescale_v1_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(result=summary['result'],cap_decoded_exact=True,
    AR8_gate_failures=checked['gate_failures'],c_h_count=len(index))))

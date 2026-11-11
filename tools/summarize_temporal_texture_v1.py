"""Bind temporal observations and an offline candidate without runtime claims."""
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

root=args.workspace/'references/analysis/temporal_texture_v1'
reports={name:json.loads((root/name/'report.json').read_text(encoding='utf-8'))
         for name in ('analysis1','magnitude1','verification1','review1')}
assert all(r['result']=='pass' for r in reports.values())
for name in ('analysis1','magnitude1','verification1'):
    for source,digest in reports[name]['source_sha256'].items():
        assert sha(root/name/'exact_sources'/source)==digest,(name,source)
assert sha(root/'review1/executed_review.py')==reports['review1']['source_sha256']
a,m,v,r=(reports[name] for name in ('analysis1','magnitude1','verification1','review1'))
assert m['temporal_report_sha256']==v['temporal_report_sha256']==sha(root/'analysis1/report.json')
assert v['candidate_report_sha256']==sha(root/'magnitude1/report.json')
assert sha(root/'magnitude1/candidate_moments.npz')==m['model_sha256']
for row in a['observations']:
    assert sha(root/'analysis1'/(row['name']+'.npz'))==row['observation_sha256']
for row in m['trials']:
    assert sha(root/'magnitude1'/(row['name']+'.wav'))==row['wav_sha256']
for row in r['files']:
    assert sha(root/'review1'/(row['name']+'.wav'))==row['output_sha256']
assert sha(root/'review1/review.html')==r['page_sha256']
assert all(row.get('status')==200 for row in r['http'])
prior=args.workspace/'baselines/residual_motion_v1'
assert sha(prior/'manifest.json')==a['prior_manifest_sha256']==m['prior_manifest_sha256']
for name,digest in a['frozen_inputs'].items():assert sha(prior/name)==digest
with (repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig',newline='') as stream:index=list(csv.DictReader(stream))
assert len(index)==v['c_h_count']==a['c_h_count']==436
for row in index:assert sha(repo/row['文件'])==row['SHA-256']
assert not subprocess.check_output(['git','diff','HEAD','--','*.c','*.h'],cwd=repo).strip()
accepted=json.loads((repo/'research/coherent_low_v1_acceptance.json').read_text(encoding='utf-8'))
assert sha(repo/accepted['model'])==accepted['model_sha256']
assert sha(repo/'voices/dna_bank_v1/V10 Exterior.model')==accepted['dna_model_sha256']
fixed=next(row for row in a['observations'] if row['name']=='fixed_A_reference')
baseline=next(row for row in a['observations'] if row['name']=='fixed_DNA_LF')
baseline_score=baseline['fixed_target_comparison']['covariance_relative_distance_median_LR'][0]
target_power=np.array(fixed['summary']['mean_power_LR'])
trials=[]
for trial in v['trials']:
    original=next(row for row in m['trials'] if row['name']==trial['name'])
    power=10*np.log10(np.array(trial['summary']['mean_power_LR'])/target_power)
    trials.append(dict(name=trial['name'],seed=original['seed'],amount=original['amount'],
        covariance_relative_distance_LR=trial['covariance_relative_distance_median_LR'],
        relative_covariance_distance_reduction_percent_L=100*(1-trial['covariance_relative_distance_median_LR'][0]/baseline_score),
        high_cv_LR=trial['summary']['median_cv_LR'][6:],
        high_band_power_error_db_LR=power[6:].tolist(),
        high_0p1_4Hz_variance_fraction_LR=trial['summary']['modulation_fraction'][0][6:],
        peak=trial['peak']))
source_paths=[Path(__file__),repo/'tools/freeze_temporal_texture_v1.py',
    repo/'research/temporal_texture_v1_plan.json',repo/'tools/analyze_temporal_texture_v1.py',
    repo/'tools/explore_harmonic_magnitude_v1.py',repo/'tools/verify_harmonic_magnitude_v1.py',
    repo/'tools/make_magnitude_review_v1.py',repo/'tools/sustain_osc_v1/oracle.py',
    repo/'tools/drive_evidence_v1/sources.py',repo/'tools/residual_osc_v1/spectrum.py',
    *sorted((repo/'tools/temporal_texture_v1').glob('*.py')),
    *sorted((repo/'tools/harmonic_magnitude_v1').glob('*.py'))]
summary=dict(schema='vsl.temporal-texture-summary/1',date='2026-11-12',result='pass',
    base_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
    evidence_root=str(root),observations=len(a['observations']),known_envelope_controls=len(a['controls']),
    raw_cases=[dict(name=row['name'],provenance=row['provenance'],summary={k:row['summary'][k] for k in
        ('blocks','median_cv_LR','median_abs_crossband_correlation_LR','mean_power_LR')})
        for row in a['observations'] if row['kind']=='raw_recording'],
    paired_reference=dict(frames=58424,complete_blocks=1,high_cv_LR=fixed['summary']['median_cv_LR'][6:],
        high_0p1_4Hz_variance_fraction_LR=fixed['summary']['modulation_fraction'][0][6:],
        median_abs_crossband_correlation_LR=fixed['summary']['median_abs_crossband_correlation_LR']),
    accepted_generator=dict(high_cv_LR=baseline['summary']['median_cv_LR'][6:],
        covariance_relative_distance_LR=baseline['fixed_target_comparison']['covariance_relative_distance_median_LR'],
        high_0p1_4Hz_variance_fraction_LR=baseline['summary']['modulation_fraction'][0][6:]),
    surrogate_maximum_spectral_matrix_relative_error=max(row.get('complete_spectral_matrix_relative_error',0) for row in a['observations']),
    surrogate_crossband_abs_correlation_range_L=[min(row['summary']['median_abs_crossband_correlation_LR'][0]
        for row in a['observations'] if row['kind']=='offline_diagnostic'),max(row['summary']['median_abs_crossband_correlation_LR'][0]
        for row in a['observations'] if row['kind']=='offline_diagnostic')],
    candidate=dict(training=m['training'],legacy_C_error=m['legacy_C_max_abs_error'],
        static_control_error=m['static_control_max_error'],trials=trials,
        known_power_error_db=max(abs(p) for c in v['controls'] for p in c['power_error_db']),
        known_complex_coherence_error=max(p for c in v['controls'] for p in c['complex_coherence_error']),
        exact_mono=v['exact_mono_passed'],maximum_float32_cv_drift=max(t['maximum_float32_cv_drift'] for t in v['trials']),
        slow_envelope_alignment='not_established;0.1–4Hz variance fraction remains below reference',
        qualification='offline_candidate_only; same short target, not perceived realism or unseen recording validation'),
    review=dict(page=r['page'],page_sha256=r['page_sha256'],http=r['http'],gain=r['common_gain'],
        seed_selection=r['seed_selection'],browser_interaction_verified=False,human_accepted=False),
    c_h_count=len(index),c_index_sha256=sha(repo/'handoff/C文件索引.csv'),accepted_models_unchanged=True,
    runtime_changes=False,model_bank_changed=False,new_state_mapping=False,human_accepted=False,
    source_sha256={p.relative_to(repo).as_posix():sha(p) for p in source_paths},
    evidence_sha256={p.relative_to(root).as_posix():sha(p) for p in sorted(root.rglob('*'))
                     if p.is_file() and '__pycache__' not in p.parts},
    prior_manifest_sha256=a['prior_manifest_sha256'],
    input_metadata_sha256={name:sha(args.workspace/name) for name in
        ('references/segments_v1.json','references/approval_manifest.json')},
    limits=a['limits']+m['limits']+v['limits']+[
        'CV of near-silent residual solo bands can be leakage dominated and is not interpreted as missing engine detail',
        'Raw later-A and stationary passages are dynamic contexts; large shared envelopes do not identify constant-load texture',
        '50percent crossfade changes mean spectral power; covariance scores are not a level-controlled perceptual result'])
(repo/'research/temporal_texture_v1_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(result='pass',observations=summary['observations'],candidate_trials=len(trials),
    known_power_error_db=summary['candidate']['known_power_error_db'],c_h_count=len(index))))

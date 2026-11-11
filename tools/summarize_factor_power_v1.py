"""Bind finite-power and window observations without promoting a sound model."""
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
from drive_evidence_v1.sources import sha

root=args.workspace/'references/analysis/factor_power_v1'
power=json.loads((root/'analysis1/report.json').read_text(encoding='utf-8'))
windows=json.loads((root/'windows1/report.json').read_text(encoding='utf-8'))
assert power['result']==windows['result']=='pass'
for folder,report in (('analysis1',power),('windows1',windows)):
    for name,digest in report['source_sha256'].items():assert sha(root/folder/'exact_sources'/name)==digest,(folder,name)
prior=args.workspace/'baselines/magnitude_timescale_v1'
assert sha(prior/'manifest.json')==power['prior_manifest_sha256']
for name,digest in power['frozen_inputs'].items():assert sha(prior/name)==digest,name
for path,digest in windows['input_sha256'].items():assert sha(path)==digest,path
for row in windows['observations']:assert sha(root/'windows1'/(row['name']+'.npz'))==row['score_npz_sha256']
with (repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig',newline='') as stream:index=list(csv.DictReader(stream))
assert len(index)==436
for row in index:assert sha(repo/row['文件'])==row['SHA-256'],row['文件']
assert not subprocess.check_output(['git','diff','HEAD','--','*.c','*.h'],cwd=repo).strip()
accepted=json.loads((repo/'research/coherent_low_v1_acceptance.json').read_text(encoding='utf-8'))
assert sha(repo/accepted['model'])==accepted['model_sha256']
assert sha(repo/'voices/dna_bank_v1/V10 Exterior.model')==accepted['dna_model_sha256']
failed=next(r for r in power['controls'] if r['seed']==62017)
window_rows=[]
for ob in windows['observations']:
    if ob['name']=='known_single_carrier_AM':
        window_rows.append(dict(name=ob['name'],meaning='Only harmonic5 positive-control error is interpreted; sparse-target factor projections are excluded',
            maximum_log_error_db=max(r['known_AM_log_error_db'] for r in ob['configurations'])))
        continue
    if ob['name']=='known_stationary_OSC':
        window_rows.append(dict(name=ob['name'],meaning='Near-zero factor variance; lag ratios are not interpreted',
            maximum_log_motion_db=max(r['log_motion_db'] for r in ob['configurations'])))
        continue
    window_rows.append(dict(name=ob['name'],scope=ob['scope'],configurations=ob['configurations']))
sources=[Path(__file__),repo/'tools/freeze_factor_power_v1.py',repo/'tools/analyze_factor_power_v1.py',
    repo/'tools/analyze_factor_windows_v1.py',repo/'research/factor_power_v1_plan.json',
    repo/'research/factor_window_v1_plan.json',*sorted((repo/'tools/factor_power_v1').glob('*.py'))]
summary=dict(schema='vsl.factor-power-summary/1',date='2026-11-12',result='diagnostics_pass_only',
    evidence_root=str(root),base_commit=power['base_commit'],
    power=dict(expected_squared_envelope_error=power['expected_power_error'],
        quadrature_variance_relative_error=power['quadrature_variance_relative_error'],
        predicted_16s_standard_deviation=power['predicted_finite_power_sd'],ensemble=power['ensemble'],
        maximum_frozen_Welch_reconstruction_error_db=max(r['reconstructed_maximum_error_db'] for r in power['controls']),
        previously_failed_seed=failed,prior_16s_gate_result=power['prior_16s_gate_result'],
        interpretation=power['decision']),
    windows=dict(observations=window_rows,
        configurations=sum(len(r['configurations']) for r in windows['observations']),
        maximum_direct_DFT_error=max(r['direct_DFT_relative_error'] for ob in windows['observations'] for r in ob['configurations']),
        decision='Known fixed detuning can create lag4 dominance without source AM; window dependence prevents physical interpretation or blind transfer of frozen AR8 factors'),
    candidate_AR8_qualification='Original16s gate remains not_passed; finite-run failure is not treated as proof of biased ensemble normalization; no new model or adoption',
    c_h_count=len(index),c_index_sha256=sha(repo/'handoff/C文件索引.csv'),
    accepted_models_unchanged=True,runtime_changes=False,models_changed=False,state_mapping_changed=False,human_accepted=False,
    current_source_sha256={p.relative_to(repo).as_posix():sha(p) for p in sources},
    evidence_sha256={p.relative_to(root).as_posix():sha(p) for p in sorted(root.rglob('*'))
        if p.is_file() and '__pycache__' not in p.parts},
    prior_manifest_sha256=power['prior_manifest_sha256'],
    input_sha256=windows['input_sha256'],
    limits=power['limits']+windows['limits']+[
        'Mathematical and empirical ensemble checks do not replace the old per-run gate or establish perceptual quality',
        'Known stationary-control variances/lag ratios are not fitted physical engine modulation parameters',
        'Hann2/Hann4 central-bin noise gains and smoothing differ from rect1; no direct energy/variance replacement',
        'Original fixed A is short and dynamic; the cause of all real temporal variations remains unidentified',
        'Existing listening review pending; no new page, C test rerun, hardware or spatial acceptance'])
(repo/'research/factor_power_v1_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(result=summary['result'],frozen_Welch_error=summary['power']['maximum_frozen_Welch_reconstruction_error_db'],
    window_configurations=summary['windows']['configurations'],c_h_count=len(index))))

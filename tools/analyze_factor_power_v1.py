"""Explain the frozen short-run power failure with independent moment checks."""
import argparse
import csv
import json
from pathlib import Path
import shutil
import subprocess
import sys

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True)
parser.add_argument('--out',type=Path,required=True)
args=parser.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
from drive_evidence_v1.sources import sha
from factor_power_v1.moments import expectation,finite_variance,interval_energy
from factor_power_v1.simulation import ensemble,reconstruct
from residual_osc_v1.spectrum import matrices

args.out.mkdir(parents=True,exist_ok=False)
plan_path=repo/'research/factor_power_v1_plan.json';plan=json.loads(plan_path.read_text(encoding='utf-8'))
paths=[Path(__file__),plan_path,repo/'tools/drive_evidence_v1/sources.py',
    repo/'tools/residual_osc_v1/spectrum.py',*sorted((repo/'tools/factor_power_v1').glob('*.py'))]
for path in paths:
    target=args.out/'exact_sources'/path.relative_to(repo);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
report=dict(schema='vsl.factor-power/1',result='running',source_sha256={p.relative_to(repo).as_posix():sha(p) for p in paths},
    base_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),controls=[])
(args.out/'metadata.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')

try:
    frozen=args.workspace/'baselines/magnitude_timescale_v1'
    manifest=json.loads((frozen/'manifest.json').read_text(encoding='utf-8'));expected={r['path']:r['sha256'] for r in manifest['files']}
    report['prior_manifest_sha256']=sha(frozen/'manifest.json');report['frozen_inputs']={}
    for name in ('evidence/factor8_1/factor_profiles.npz','evidence/factor8_verification2/report.json'):
        assert sha(frozen/name)==expected[name],name;report['frozen_inputs'][name]=expected[name]
    original=json.loads((frozen/'evidence/factor8_verification2/report.json').read_text(encoding='utf-8'))
    assert original['result']=='not_passed'
    archive=np.load(frozen/'evidence/factor8_1/factor_profiles.npz')
    profiles=[{key:archive[key][j] for key in archive.files} for j in plan['profile_indices']]
    weights=np.array(plan['log_weights']);steps=round(plan['duration_seconds']*plan['sample_rate']/plan['update_frames'])
    mean=expectation(profiles,weights,plan['quadrature_orders'][-1],plan['hermite_order'])
    mean_error=float(abs(mean-1).max());assert mean_error<plan['tolerances']['expected_power_absolute'],mean_error
    variances=[]
    for order in plan['quadrature_orders']:
        variance,covariance=finite_variance(profiles,weights,steps,order);variances.append(variance)
    variance_error=float(np.max(abs(variances[0]-variances[1])/variances[1]))
    assert variance_error<plan['tolerances']['quadrature_variance_relative'],variance_error
    prediction=variances[-1];standard=np.sqrt(prediction)
    report.update(expected_power_error=mean_error,quadrature_variance_relative_error=variance_error,
        predicted_finite_power_variance=prediction.tolist(),predicted_finite_power_sd=standard.tolist())
    print(json.dumps(dict(expected_error=mean_error,predicted_sd=standard.tolist())),flush=True)
    simulated=ensemble(profiles,weights,steps,plan['ensemble_replicates'],plan['ensemble_seed'],plan['quadrature_orders'][0])
    np.savez_compressed(args.out/'independent_ensemble.npz',mean_envelope_power=simulated)
    observed_mean=simulated.mean(axis=0);observed_variance=simulated.var(axis=0,ddof=1)
    z=(observed_mean-1)/np.sqrt(prediction/len(simulated))
    relative=abs(observed_variance/prediction-1)
    assert max(abs(z))<plan['tolerances']['ensemble_mean_standard_errors'],z
    assert max(relative)<plan['tolerances']['ensemble_variance_relative'],relative
    report['ensemble']=dict(replicates=len(simulated),mean=observed_mean.tolist(),variance=observed_variance.tolist(),
        mean_error_standard_errors=z.tolist(),variance_relative_error=relative.tolist(),
        empirical_power_db_quantiles=np.quantile(10*np.log10(simulated),[.025,.5,.975],axis=0).tolist(),
        per_run_0p5dB_exceedance_fraction=(abs(10*np.log10(simulated))>=.5).mean(axis=0).tolist())
    for seed in plan['original_seeds']:
        audio,energy,factors=reconstruct(profiles,weights,plan,seed)
        old=next(r for r in original['controls'] if r['seed']==seed)
        observed=matrices(audio,plan['bands']);deltas=[]
        for row in observed:
            deltas.extend((10*np.log10(np.array(row['power'])/(np.array(plan['carrier_amplitudes_LR'])**2/2))).tolist())
        difference=float(abs(np.array(deltas)-old['power_error_db']).max())
        assert difference<plan['tolerances']['reconstructed_Welch_error_db'],difference
        continuous=interval_energy(factors[:-1],factors[1:],profiles,weights,plan['quadrature_orders'][-1]).mean(axis=0)
        report['controls'].append(dict(seed=seed,Welch_error_db=deltas,prior_Welch_error_db=old['power_error_db'],
            reconstructed_maximum_error_db=difference,discrete_envelope_power=energy.tolist(),
            continuous_quadrature_envelope_power=continuous.tolist(),
            envelope_error_in_predicted_standard_deviations=((energy-1)/standard).tolist()))
    with (repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig',newline='') as stream:index=list(csv.DictReader(stream))
    assert len(index)==436
    for row in index:assert sha(repo/row['文件'])==row['SHA-256'],row['文件']
    report.update(result='pass',c_h_count=len(index),c_index_sha256=sha(repo/'handoff/C文件索引.csv'),
        prior_16s_gate_result='not_passed; unchanged',runtime_changes=False,models_changed=False,human_accepted=False,
        decision='Known short-run failure is consistent with finite stochastic envelope variation; no evidence here of a biased expected-power correction',
        limits=[plan['scope'],'The exact Gaussian statement covers normalized squared envelope amplitude, not arbitrary filtered/mixed audio power',
        'Empirical quantiles/exceedances use512 independent synthetic runs, not a guaranteed per-run bound',
        'No per-WAV gain normalization, new synthesis model, hearing or real-engine causal validation'])
except Exception as exc:
    report.update(result='failed',error=repr(exc));raise
finally:
    (args.out/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(result=report['result'],ensemble_mean=report['ensemble']['mean'],controls=len(report['controls']))),flush=True)

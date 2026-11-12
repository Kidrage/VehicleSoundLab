"""Bind C build, density renders, meter controls and review to handoff hashes."""
import argparse
import csv
import importlib.util
import json
from pathlib import Path
import shutil
import statistics
import sys

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True)
args=parser.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from drive_evidence_v1.sources import sha
from residual_osc_v1.spectrum import matrices,error

root=args.workspace/'references/analysis/residual_dense_v1'
out=root/'verification1';out.mkdir(exist_ok=False)
attempts={name:json.loads((root/name/'report.json').read_text(encoding='utf-8')) for name in ('build1','run1','envelope1','review1')}
assert [attempts[k]['result'] for k in attempts]==['pass','technical_pass_only','pass','pass']
inputs={}
for name,record in attempts.items():
    for path,digest in record['source_sha256'].items():
        assert sha(root/name/'exact_sources'/path)==digest,(name,path)
        assert sha(repo/path)==digest,(name,path)
    for path,digest in record.get('input_sha256',{}).items():assert sha(path)==digest,path
    inputs.update(record.get('input_sha256',{}))
build=attempts['build1'];run=attempts['run1'];review=attempts['review1']
assert build['prior436_C_sources_unchanged'] and all(x['exit_code']==0 for x in build['commands'])
assert len(build['commands'])==4 and run['density_qualified'] and len(run['trials'])==12 and len(run['benchmarks'])==30
assert not run['human_accepted'] and not run['driver_changes'] and not review['human_accepted']
for path,digest in build['binaries'].items():
    assert sha(path)==digest;shutil.copy2(path,out/Path(path).name)
index=repo/'handoff/C文件索引.csv'
with index.open(encoding='utf-8-sig',newline='') as stream:rows=list(csv.DictReader(stream))
assert len(rows)==442
spec=importlib.util.spec_from_file_location('vsl_current_index',repo/'handoff/tools/index_sources.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
assert [tuple(row.values()) for row in rows]==list(module.code_rows())
prior=args.workspace/'baselines/line_density_v1/docs/C文件索引.csv'
with prior.open(encoding='utf-8-sig',newline='') as stream:old=list(csv.DictReader(stream))
current={row['文件']:row for row in rows};assert len(old)==436
for row in old:assert current[row['文件']]==row,row['文件']
plan=json.loads((repo/'research/residual_dense_v1_plan.json').read_text(encoding='utf-8'))
line_plan=json.loads((repo/'research/line_density_v1_plan.json').read_text(encoding='utf-8'))
for trial in run['trials']:
    for config in trial['concentration']:
        assert config['direct_DFT_relative_error']<line_plan['tolerances']['direct_DFT_relative']
        assert config['parseval_relative_error']<line_plan['tolerances']['parseval_relative']
reference,_=sf.read(args.workspace/'baselines/residual_motion_v1/evidence/fit1/reference.wav',always_2d=True)
target=matrices(reference);decoded=[]
for trial in run['trials']:
    for key in ('cloud','mix'):
        path=root/'run1/raw'/f'{key}_{trial["peak"]}_{trial["seed"]}.wav'
        assert sha(path)==trial[key+'_sha256']
        audio,rate=sf.read(path,always_2d=True)
        assert rate==48000 and audio.shape==(768000,2) and np.isfinite(audio).all()
        if key=='mix':
            errors=error(target,matrices(audio[plan['warmup_frames']:]))
            maximum=max(abs(v) for row in errors for v in row['power_delta_db'])
            coherence=max(row['complex_coherence_error'] for row in errors)
            assert abs(maximum-trial['maximum_power_error_db'])<1e-12
            assert maximum<plan['tolerances']['mixed_band_power_error_db'] and coherence<plan['tolerances']['mixed_complex_coherence_error']
            decoded.append(dict(peak=trial['peak'],seed=trial['seed'],power_error_db=maximum,complex_coherence_error=coherence))
    if trial['peak']==32:assert trial['baseline32_samples_exact']
timings=[]
for block in plan['benchmark_blocks']:
    for peak in [0]+plan['peaks']:
        selected=[r for r in run['benchmarks'] if r['block']==block and r['peak']==peak]
        ratios=[r['process_ms']/next(x['process_ms'] for x in run['benchmarks'] if x['block']==block and x['round']==r['round'] and x['peak']==0) for r in selected]
        timings.append(dict(block=block,peak=peak,carriers=selected[0]['carriers'],voice_bytes=selected[0]['voice_bytes'],
            paired_process_ratio_to_legacy_median=statistics.median(ratios),paired_process_ratio_range=[min(ratios),max(ratios)],
            block_median_ms=statistics.median(r['median_ms'] for r in selected),maximum_ms=max(r['maximum_ms'] for r in selected),
            overruns=sum(r['overruns'] for r in selected)))
densities=[]
for peak in plan['peaks']:
    selected=[r for r in run['trials'] if r['peak']==peak]
    high=[r['concentration'][1]['rows'][0]['concentration_LR'][-1][0] for r in selected]
    densities.append(dict(peak=peak,counts=selected[0]['timing']['counts'],allocated_carriers=selected[0]['timing']['carriers'],
        high_16cycle_3bin_concentration_L_range=[min(high),max(high)],
        high_cloud_power_cv_L_range=[min(r['cloud_envelope']['power_cv_LR'][-1][0] for r in selected),max(r['cloud_envelope']['power_cv_LR'][-1][0] for r in selected)],
        high_cloud_modulation_peak_hz_L=[r['cloud_envelope']['envelope_peak_hz_LR'][-1][0] for r in selected]))
verification=dict(result='pass',decoded_mixes=decoded,prior436_ownership_and_C_hashes_preserved=True,c_h_count=442,
    old32_samples_exact_all_three_seeds=True,old32_state_contract_pass=True,default_ctests=40,standalone_ctests=1,
    browser_interaction_checked=False,human_accepted=False)
(out/'report.json').write_text(json.dumps(verification,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
shutil.copy2(Path(__file__),out/Path(__file__).name)
sources=[p for directory in ('modules/residual_dense','experiments/residual_dense_v1','tools/residual_dense_v1')
    for p in sorted((repo/directory).glob('*')) if p.is_file()]
sources += [repo/name for name in ('tools/build_residual_dense_v1.py','tools/run_residual_dense_v1.py',
    'tools/check_residual_dense_envelope_v1.py','tools/review_residual_dense_v1.py','tools/finalize_residual_dense_v1.py',
    'tools/freeze_residual_dense_v1.py','research/residual_dense_v1_plan.json','handoff/tools/index_sources.py')]
summary=dict(schema='vsl.residual-dense-summary/1',date='2026-11-12',result='isolated_C_experiment_only',
    attempts=[dict(folder=name,result=record['result']) for name,record in attempts.items()],
    evidence_root=str(root),c_h_count=442,c_index_sha256=sha(index),prior436_C_sources_and_ownership_unchanged=True,
    new_C_H_count=6,default_ctests=40,standalone_ctests=1,old32_three_seed_samples_and_contract_state_exact=True,
    maximum_direct_sum_error_FS=max(x['direct_error_FS'] for x in run['known_controls']),
    maximum_known_power_error_db=max(x['maximum_power_error_db'] for x in run['known_controls']),
    maximum_known_complex_coherence_error=max(x['maximum_complex_coherence_error'] for x in run['known_controls']),
    maximum_mixed_power_error_db=max(x['maximum_power_error_db'] for x in run['trials']),
    maximum_mixed_complex_coherence_error=max(x['maximum_complex_coherence_error'] for x in run['trials']),
    envelope_control_maximum_cv_error=max(x['cv_absolute_error'] for x in attempts['envelope1']['controls']),
    densities=densities,benchmarks=timings,review_url=review['url'],review_audio_count=len(review['audio']),
    review_maximum_peak=max(x['peak'] for x in review['audio']),browser_interaction_checked=False,
    default_models_changed=False,driver_changes=False,old_binaries_rebuilt=False,human_accepted=False,
    current_source_sha256={p.relative_to(repo).as_posix():sha(p) for p in sources},
    input_sha256=inputs,evidence_sha256={p.relative_to(root).as_posix():sha(p) for p in sorted(root.rglob('*')) if p.is_file() and '__pycache__' not in p.parts},
    limits=run['limits']+['Only one predeclared seed is used on the review page; three seeds were measured, no best-seed selection',
        'High concentration approaches a floor with the retained50percent harmonic model; increasing density alone does not reproduce the reference',
        'Observed meter CV and peak frequency can arise from stationary carrier beating, window smoothing and envelope sampling; no new AM model was fitted',
        'The caller-owned dense voice uses524352bytes at every density; current frequency/weight recurrence is deliberately unoptimized',
        'HTTP bytes andFFmpeg decode are checked; browser interaction, human listening, native-device integration and full-driver timing are not established'])
(repo/'research/residual_dense_v1_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(result=summary['result'],C_H=442,maximum_mixed_power_error_db=summary['maximum_mixed_power_error_db'],review_audio=summary['review_audio_count'])))

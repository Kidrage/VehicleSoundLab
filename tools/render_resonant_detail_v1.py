"""Render fixed-budget resonant replacement across seeds; no per-clip gain fit."""
import argparse,csv,json,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True);p.add_argument('--fit',type=Path,required=True)
p.add_argument('--out',type=Path,required=True);a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from drive_evidence_v1.sources import sha
from residual_osc_v1.spectrum import matrices,error
from resonant_detail_v1.voice import render
from dna_texture_v2.observe import observe

a.out.mkdir(parents=True,exist_ok=False)
r=dict(schema='vsl.resonant-detail-render/1',result='running',trials=[],source_sha256={},input_sha256={})
try:
    fitted=json.loads((a.fit/'report.json').read_text(encoding='utf-8'))
    assert fitted['result']=='fit_and_known_controls_pass'
    for name,digest in fitted['source_sha256'].items():assert sha(repo/name)==digest,name
    for name in ('detail_model.json','report.json'):r['input_sha256'][str(a.fit/name)]=sha(a.fit/name)
    model=json.loads((a.fit/'detail_model.json').read_text(encoding='utf-8'));plan=model['plan']
    assert sha(a.fit/'detail_model.json')==fitted['model_sha256']
    paths=[Path(__file__),repo/'tools/dna_texture_v2/observe.py',repo/'tools/drive_evidence_v1/sources.py',
           *sorted((repo/'tools/resonant_detail_v1').glob('*.py'))]
    for path in paths:
        target=a.out/'exact_sources'/path.relative_to(repo);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
        r['source_sha256'][path.relative_to(repo).as_posix()]=sha(path)
    raw=a.out/'raw';raw.mkdir();frames=round(plan['seconds']*48000)
    lf_path=a.workspace/'baselines/coherent_low_v1/evidence/raw/measured.wav'
    assert sha(lf_path)==fitted['input_sha256'][str(lf_path)]
    low,rate=sf.read(lf_path,always_2d=True);assert rate==48000
    low=low[:frames]*fitted['low_scale']
    ref_path=a.workspace/'baselines/residual_motion_v1/evidence/fit1/reference.wav'
    assert sha(ref_path)==fitted['input_sha256'][str(ref_path)]
    reference,rate=sf.read(ref_path,always_2d=True);target=matrices(reference)
    warm=plan['review_crop_frames'][0]
    diagnostic=json.loads((repo/'research/dna_texture_v2_plan.json').read_text(encoding='utf-8'))
    sf.write(raw/'reference.wav',reference,48000,subtype='FLOAT')
    base=next(v for v in model['trials'] if v['amount']==0)
    dna,rate=sf.read(a.fit/(base['label']+'_dna.wav'),always_2d=True)
    original=dna+low;sf.write(raw/'original.wav',original,48000,subtype='FLOAT')
    r['baseline_observation']=observe(original[warm:warm+len(reference)],diagnostic)
    for seed in plan['detail_seeds']:
        bands=render(model['filters'],frames,seed,plan)
        assert bands.shape==(frames,len(model['filters'])) and np.isfinite(bands).all()
        sf.write(raw/f'excitation_{seed}.wav',bands,48000,subtype='FLOAT')
        for trial in model['trials']:
            if trial['amount']==0:continue
            dna_path=a.fit/(trial['label']+'_dna.wav');assert sha(dna_path)==trial['DNA_stem_sha256']
            dna,rate=sf.read(dna_path,always_2d=True);g=np.array(trial['noise_amplitude_gain'])
            left=bands@g;right=bands@(g*np.array(model['stereo_R_over_L']))
            detail=np.column_stack((left,right));mixed=dna+low+detail
            name=f"{trial['label']}_{seed}"
            sf.write(raw/(name+'_detail.wav'),detail,48000,subtype='FLOAT')
            path=raw/(name+'_mix.wav');sf.write(path,mixed,48000,subtype='FLOAT')
            # Verify the delivered float file, not only the pre-write array.
            delivered,rate=sf.read(path,always_2d=True);assert rate==48000
            errors=error(target,matrices(delivered[warm:]))
            power=max(abs(v) for b in errors for v in b['power_delta_db'])
            covariance=max(b['complex_coherence_error'] for b in errors)
            observation=observe(delivered[warm:warm+len(reference)],diagnostic)
            r['trials'].append(dict(name=name,seed=seed,amount=trial['amount'],file=path.name,sha256=sha(path),
                maximum_mean_power_error_db=power,maximum_complex_coherence_error=covariance,power_errors=errors,
                power_gate=power<plan['checks']['maximum_mixed_band_power_error_db'],
                peak_FS_after_common_gain=float(abs(delivered).max()*plan['output_gain']),
                observation=observation))
            print(json.dumps(dict(seed=seed,amount=trial['amount'],maximum_power_error_db=power,
                repeat_6_8k=observation[-1]['repeat'][0]['maximum_repeat'])),flush=True)
    with (repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig') as f:index=list(csv.DictReader(f))
    assert len(index)==478
    for row in index:assert sha(repo/row['文件'])==row['SHA-256']
    passed=all(v['power_gate'] and v['peak_FS_after_common_gain']<.95 for v in r['trials'])
    r.update(result='render_technical_pass' if passed else 'render_gate_not_passed',C_H_unchanged=478,
        independent_LF_file_unchanged=True,per_seed_gain_compensation=False,human_accepted=False,
        limits=['Same1.217s normalized A training source, not independent engine/state validation',
                'Rank-one shared detail stereo reflects near-mono source; no new width information',
                'No C/live/native/take/default changes; poles and diagnostic repeats are not physical mode/noise-fraction claims',
                'Low harmonic rows and frozen LF stem preserved, not an exact lowpass-output equality claim'])
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:(a.out/'report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(result=r['result'],trials=len(r['trials']))))

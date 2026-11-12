"""Generate stationary-low detail through the unchanged shared voice kernel."""
import argparse,csv,json,shutil,sys
from pathlib import Path

p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--fit',type=Path,required=True);p.add_argument('--audit',type=Path,required=True)
p.add_argument('--out',type=Path,required=True);a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from drive_evidence_v1.sources import sha
from residual_osc_v1.spectrum import matrices,error
from resonant_detail_v1.voice import render
from dna_texture_v2.observe import analytic_band,repeat

a.out.mkdir(parents=True,exist_ok=False)
r=dict(schema='vsl.idle-resonant-render/1',result='running',trials=[],source_sha256={},input_sha256={})
try:
    fit=json.loads((a.fit/'report.json').read_text(encoding='utf-8'))
    assert fit['result']=='fit_and_fractional_period_controls_pass'
    for name,digest in fit['source_sha256'].items():assert sha(repo/name)==digest,name
    for name,digest in fit['input_sha256'].items():assert sha(Path(name))==digest,name
    model=json.loads((a.fit/'detail_model.json').read_text(encoding='utf-8'));plan=model['plan']
    assert sha(a.fit/'detail_model.json')==fit['model_sha256']
    for path in [a.fit/'report.json',a.fit/'detail_model.json',a.audit/'raw_reference.wav',a.audit/'report.json']:
        r['input_sha256'][str(path)]=sha(path)
    for path in [Path(__file__),repo/'tools/drive_evidence_v1/sources.py',repo/'tools/residual_osc_v1/spectrum.py',
                 repo/'tools/dna_texture_v2/observe.py',repo/'tools/sustain_osc_v1/oracle.py',
                 *sorted((repo/'tools/idle_texture_v1').glob('*.py')),*sorted((repo/'tools/resonant_detail_v1').glob('*.py'))]:
        target=a.out/'exact_sources'/path.relative_to(repo);target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,target);r['source_sha256'][path.relative_to(repo).as_posix()]=sha(path)
    reference,rate=sf.read(a.audit/'raw_reference.wav',always_2d=True);assert rate==48000
    target=matrices(reference,plan['bands_hz']);warm=plan['crop_start_frames']
    audit=json.loads((a.audit/'report.json').read_text(encoding='utf-8'))
    metric=dict(audit['plan'],acoustic_cycle_frames=audit['nominal_cycle_frames'])
    original,rate=sf.read(a.fit/'add_only_DNA.wav',always_2d=True);assert rate==48000
    raw=a.out/'raw';raw.mkdir();sf.write(raw/'original.wav',original,48000,subtype='FLOAT')
    sf.write(raw/'reference.wav',reference,48000,subtype='FLOAT')
    low_original=matrices(original[warm:],[(20,300)])
    ratios=np.array(model['stereo_R_over_L'])
    for seed in plan['detail_seeds']:
        bands=render(model['filters'],plan['seconds']*48000,seed,plan)
        assert np.isfinite(bands).all()
        sf.write(raw/f'excitation_{seed}.wav',bands,48000,subtype='FLOAT')
        for trial in model['trials']:
            path=a.fit/(trial['label']+'_DNA.wav');assert sha(path)==trial['DNA_stem_sha256']
            dna,rate=sf.read(path,always_2d=True);assert rate==48000
            gains=np.array(trial['detail_gain'])
            detail=np.column_stack((bands@gains,bands@(gains*ratios)))
            name=f"{trial['label']}_{seed}";file=raw/(name+'_mix.wav')
            sf.write(file,dna+detail,48000,subtype='FLOAT')
            sf.write(raw/(name+'_detail.wav'),detail,48000,subtype='FLOAT')
            mixed,rate=sf.read(file,always_2d=True);assert rate==48000 and np.isfinite(mixed).all()
            errors=error(target,matrices(mixed[warm:],plan['bands_hz']))
            power=max(abs(v) for b in errors for v in b['power_delta_db'])
            coherence=max(b['complex_coherence_error'] for b in errors)
            low=error(low_original,matrices(mixed[warm:],[(20,300)]))
            observations=[];block=mixed[warm:warm+len(reference)]
            for band in metric['bands_hz']:
                corr,direct=repeat(analytic_band(block,band,metric),metric)
                observations.append(dict(band_hz=band,repeat=corr,direct_error=direct))
            peak=float(abs(mixed).max()*plan['output_gain'])
            passed=power<plan['checks']['maximum_mixed_power_error_db'] and coherence<plan['checks']['maximum_coherence_error'] and peak<plan['checks']['maximum_peak_FS']
            r['trials'].append(dict(label=trial['label'],amount=trial['amount'],seed=seed,file=file.name,sha256=sha(file),
                maximum_power_error_db=power,maximum_complex_coherence_error=coherence,
                peak_FS_after_common_gain=peak,gate_pass=passed,power_errors=errors,
                low20_300_change_db=low[0]['power_delta_db'],observation=observations))
            print(json.dumps(dict(label=trial['label'],seed=seed,power_error_db=power,coherence_error=coherence,
                low_change_db=low[0]['power_delta_db'],gate_pass=passed)),flush=True)
    with (repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig') as f:index=list(csv.DictReader(f))
    assert len(index)==478
    for row in index:assert sha(repo/row['文件'])==row['SHA-256']
    r.update(result='render_technical_pass' if all(v['gate_pass'] for v in r['trials']) else 'render_gate_not_passed',
        C_H_unchanged=478,moving_reference_changed=False,added_low_body=False,
        per_clip_gain_compensation=False,new_room=False,new_native_or_driver_changes=False,human_accepted=False,
        limits=['Raw short-source mean and whole six-second generated mean are descriptive, not independent state validation',
            'No confirmed warm-idle/RPM or separated mechanical physical source',
            'No envelope met both half-validation and weak-depth conditions; all are flat',
            'Power/coherence/repeat controls do not establish natural engine character'])
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:(a.out/'report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(result=r['result'],trials=len(r['trials']))))

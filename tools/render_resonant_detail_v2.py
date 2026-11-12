"""Render the paired midrange candidate, preserving kernel and random streams."""
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
r=dict(schema='vsl.resonant-detail-render/2',result='running',trials=[],source_sha256={},input_sha256={})
try:
    fit=json.loads((a.fit/'report.json').read_text(encoding='utf-8'))
    assert fit['result']=='fit_and_mask_controls_pass'
    for name,digest in fit['source_sha256'].items():assert sha(repo/name)==digest,name
    for name,digest in fit['input_sha256'].items():assert sha(Path(name))==digest,name
    model=json.loads((a.fit/'detail_model.json').read_text(encoding='utf-8'));plan=model['plan']
    assert sha(a.fit/'detail_model.json')==fit['model_sha256']
    assert sha(a.fit/'protected_dna.wav')==fit['DNA_stem_sha256']
    for path in (a.fit/'report.json',a.fit/'detail_model.json',a.fit/'protected_dna.wav'):
        r['input_sha256'][str(path)]=sha(path)
    for path in [Path(__file__),repo/'tools/dna_texture_v2/observe.py',
                 repo/'tools/residual_osc_v1/spectrum.py',repo/'tools/sustain_osc_v1/oracle.py',
                 repo/'tools/drive_evidence_v1/sources.py',*sorted((repo/'tools/resonant_detail_v1').glob('*.py'))]:
        target=a.out/'exact_sources'/path.relative_to(repo);target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,target);r['source_sha256'][path.relative_to(repo).as_posix()]=sha(path)
    freeze=a.workspace/'baselines/resonant_detail_v1'
    manifest=json.loads((freeze/'manifest.json').read_text(encoding='utf-8'))
    frozen={v['path']:v['sha256'] for v in manifest['files']}
    def load_frozen(name):
        path=freeze/name;assert sha(path)==frozen[name],name
        r['input_sha256'][str(path)]=sha(path)
        x,rate=sf.read(path,always_2d=True);assert rate==48000
        return x
    reference=load_frozen('evidence/render1/raw/reference.wav')
    original=load_frozen('evidence/render1/raw/original.wav')
    good35=load_frozen('evidence/render1/raw/replace_35_8121907_mix.wav')
    raw=a.out/'raw';raw.mkdir()
    for name,x in [('reference',reference),('original',original),('replace35',good35)]:
        sf.write(raw/(name+'.wav'),x,48000,subtype='FLOAT')
        loaded,rate=sf.read(raw/(name+'.wav'),always_2d=True)
        assert np.array_equal(loaded,x)
    frames=plan['seconds']*48000;warm=plan['crop_start_frames']
    low_path=a.workspace/'baselines/coherent_low_v1/evidence/raw/measured.wav'
    assert sha(low_path)==fit['input_sha256'][str(low_path)]
    low,rate=sf.read(low_path,always_2d=True);assert rate==48000
    dna,rate=sf.read(a.fit/'protected_dna.wav',always_2d=True);assert rate==48000
    base=dna+low[:frames]*fit['low_scale']
    target=matrices(reference);original_power=matrices(original[warm:])
    diag_path=repo/'research/dna_texture_v2_plan.json'
    diagnostic=json.loads(diag_path.read_text(encoding='utf-8'))
    r['input_sha256'][str(diag_path)]=sha(diag_path)
    original_report_path=freeze/'evidence/render1/report.json'
    assert sha(original_report_path)==frozen['evidence/render1/report.json']
    r['input_sha256'][str(original_report_path)]=sha(original_report_path)
    old=json.loads(original_report_path.read_text(encoding='utf-8'))
    r['original_observation']=old['baseline_observation']
    r['original35_observation']=next(t['observation'] for t in old['trials'] if t['amount']==.35 and t['seed']==8121907)
    gains=np.array(model['detail_amplitude_gain']);ratios=np.array(model['stereo_R_over_L'])
    assert np.array_equal(gains[:4],np.zeros(4))
    for seed in plan['detail_seeds']:
        bands=render(model['filters'],frames,seed,model['kernel_plan'])
        previous=load_frozen(f'evidence/render1/raw/excitation_{seed}.wav')
        assert np.array_equal(bands.astype(np.float32),previous),seed
        detail=np.column_stack((bands@gains,bands@(gains*ratios)))
        path=raw/f'protected_{seed}_mix.wav'
        sf.write(path,base+detail,48000,subtype='FLOAT')
        sf.write(raw/f'protected_{seed}_detail.wav',detail,48000,subtype='FLOAT')
        mixed,rate=sf.read(path,always_2d=True);assert rate==48000 and np.isfinite(mixed).all()
        power=matrices(mixed[warm:]);errors=error(target,power);protection=error(original_power,power)
        active_error=max(abs(v) for b in plan['active_detail_band_indices'] for v in errors[b]['power_delta_db'])
        protected_change=max(abs(v) for b in plan['protected_measurement_band_indices'] for v in protection[b]['power_delta_db'])
        peak=float(abs(mixed).max()*plan['output_gain'])
        observations=observe(mixed[warm:warm+len(reference)],diagnostic)
        row=dict(seed=seed,file=path.name,sha256=sha(path),excitation_float_samples_exact_v1=True,
            maximum_active_power_error_db=active_error,maximum_protected_change_db=protected_change,
            peak_FS_after_common_gain=peak,power_errors=errors,protected_comparison=protection,
            observation=observations,gate_pass=active_error<plan['checks']['maximum_active_band_power_error_db']
                and protected_change<plan['checks']['maximum_protected_band_change_from_original_db']
                and peak<plan['checks']['maximum_output_peak_FS'])
        r['trials'].append(row)
        print(json.dumps(dict(seed=seed,active_error_db=active_error,protected_change_db=protected_change,
            repeat_3_6k=observations[2]['repeat'][0]['maximum_repeat'],
            repeat_6_8k=observations[3]['repeat'][0]['maximum_repeat'],gate_pass=row['gate_pass'])),flush=True)
    with (repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig') as f:index=list(csv.DictReader(f))
    assert len(index)==478
    for row in index:assert sha(repo/row['文件'])==row['SHA-256']
    r.update(result='render_technical_pass' if all(v['gate_pass'] for v in r['trials']) else 'render_gate_not_passed',
        C_H_unchanged=478,independent_LF_file_unchanged=True,no_native_default_driver_changes=True,
        per_seed_gain_compensation=False,human_accepted=False,
        limits=['Middle-band repeat is a diagnostic, not a target used to fit doses or physical noise fraction',
                'Protected harmonic rows are exact; total band signal may change through filter skirts',
                'Same normalized1.217s A context; no general engine/RPM/state validation',
                'No listening improvement inferred from energy controls'])
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:(a.out/'report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(result=r['result'],trials=len(r['trials']))))

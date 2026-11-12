"""Accepted fixed-context DNA/LF with bounded shared HF phase motion; offline."""
import argparse
import html
import json
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.request

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from scipy import signal
from drive_evidence_v1.sources import sha,read
from harmonic_magnitude_v1.legacy import parse
from phase_texture_v1.source import fit,motion
from phase_texture_v1.render import render
from residual_osc_v1.spectrum import matrices,error,BANDS

a.out.mkdir(parents=True,exist_ok=False)
r=dict(schema='vsl.phase-texture-trial/1',result='running',human_accepted=False,runtime_changed=False,
       source_sha256={},input_sha256={},trials=[],clips=[],limits=[
           'Offline same accepted A moving-tailpipe context; not physical crank/firing jitter identification',
           'Bounded shared HF phase motion is a synthesis hypothesis, not restoration of all original mechanical detail',
           'No independent HF carrier cloud, added noise, EQ brightness or per-file loudness normalization',
           'No default/source-model/native driver/UI/take changes; no device or multichannel test'])
try:
    paths=[Path(__file__),*sorted((repo/'tools/phase_texture_v1').glob('*.py')),
           repo/'tools/harmonic_magnitude_v1/legacy.py',repo/'tools/sustain_osc_v1/oracle.py',
           repo/'tools/residual_osc_v1/spectrum.py',repo/'tools/drive_evidence_v1/sources.py']
    for path in paths:
        name=path.relative_to(repo).as_posix();dest=a.out/'exact_sources'/name
        dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,dest);r['source_sha256'][name]=sha(path)
    _,r['approved_input']=read(a.workspace,'A_exterior_moving','exterior_dynamic_observation')
    def frozen(folder,name):
        root=a.workspace/'baselines'/folder
        manifest=json.loads((root/'manifest.json').read_text(encoding='utf-8'))
        path=root/name;expected=next(v['sha256'] for v in manifest['files'] if v['path']==name)
        assert sha(path)==expected; r['input_sha256'][str(path)]=expected
        r['input_sha256'][str(root/'manifest.json')]=sha(root/'manifest.json')
        x,rate=sf.read(path,always_2d=True);assert rate==48000;return x
    reference=frozen('residual_motion_v1','evidence/fit1/reference.wav')
    dna=frozen('coherent_low_v1','evidence/raw/dna.wav')
    low=frozen('coherent_low_v1','evidence/raw/measured.wav')
    assert len(dna)>=384000 and len(low)>=len(dna)
    base=dna+1.6658265329883064*low[:len(dna)]
    accepted=json.loads((repo/'research/coherent_low_v1_acceptance.json').read_text(encoding='utf-8'))
    profile=repo/'voices/dna_bank_v1/V10 Exterior.model';assert sha(profile)==accepted['dna_model_sha256']
    model=parse(profile);r['input_sha256'][str(profile)]=sha(profile)
    coords,source=fit(reference,model['mean']);r['source_phase_observation']=source
    np.savez_compressed(a.out/'source_phase_observation.npz',**coords)
    # Synthetic common static displacement is known, so retrieval must not
    # silently confuse harmonic index, stereo scale or absolute phase.
    frames=384000;hz=np.arange(1,301)*46.875
    known_mean=np.zeros((300,4));known_mean[:,0]=known_mean[:,2]=.001
    t=np.arange(48000)/48000
    known=np.sum(.001*np.cos(2*np.pi*(t[:,None]+8e-6)*hz[None,:]),axis=1)
    known_coords,known_stats=fit(np.column_stack((known,known)),known_mean)
    recovery=float(np.max(abs(known_coords['delay_seconds']-8e-6)))
    assert recovery<.126e-6,recovery
    # Retain the accepted waveform and all old low harmonic contributions.
    u=np.clip((hz-1200)/700,0,1);mask=.5-.5*np.cos(np.pi*u)
    original,zero=render(model,frames,48271,np.zeros(frames),mask)
    parity=float(np.max(abs(original-dna[:frames])))
    assert parity<2e-7 and np.max(abs(zero))==0,parity
    r['known_controls']=dict(static_delay_recovery_error_seconds=recovery,legacy_C_error_FS=parity,
                             zero_motion_delta_exact=True,low_harmonic_mask_exact_zero=bool(np.all(mask[hz<=1200]==0)))
    # Source phase may be poorly identified. In that case do not present
    # the candidate's fixed design strengths as measured engine parameters.
    reliable=(source['alternating_harmonic_delay_correlation'] is not None and
              source['alternating_harmonic_delay_correlation']>=.7 and source['boundary_fraction']<.05)
    guided=min(6.,max(2.,source['fast_delay_rms_microseconds'])) if reliable else 4.
    r['strength_policy']=dict(source_phase_qualified=reliable,full_strength_microseconds=guided,
        meaning='Source-guided bounded scale' if reliable else 'Explicit engineering hypothesis; source phase estimate not reliable enough for calibration')
    def clip(name,x):
        y=.5*x.copy();n=240;fade=np.sin(np.linspace(0,np.pi/2,n))**2
        y[:n]*=fade[:,None];y[-n:]*=fade[::-1,None]
        assert np.max(abs(y))<.95
        file=a.out/(name+'.wav');sf.write(file,y,48000,subtype='PCM_24')
        url='http://127.0.0.1:8789/'+file.relative_to(a.workspace).as_posix()
        with urllib.request.urlopen(url,timeout=10) as response:assert response.read()==file.read_bytes()
        done=subprocess.run(['ffmpeg','-v','error','-i',str(file),'-f','null','-'],capture_output=True,timeout=30)
        assert done.returncode==0
        r['clips'].append(dict(file=file.name,sha256=sha(file),url=url,peak_FS=float(np.max(abs(y))),http_decode=True))
    # All listening files use the identical time interval, gain and DNA seed.
    crop=slice(24000,384000)
    clip('accepted_original',base[crop]);clip('short_reference',reference)
    for seed in (8121907,23117,61927):
        for amount in (.5,1.):
            delay=motion(frames,seed,guided*1e-6*amount)
            generated,delta=render(model,frames,48271,delay,mask)
            assert np.array_equal(generated,original)
            candidate=base[:frames]+delta
            sf.write(a.out/f'raw_{seed}_{amount:g}.wav',candidate,48000,subtype='FLOAT')
            differences=error(matrices(base[crop]),matrices(candidate[crop]))
            # Mean changes are reported, not compensated to hide differences.
            max_power=max(abs(v) for row in differences for v in row['power_delta_db'])
            motion_psd=signal.welch(delay[24000:],fs=48000,nperseg=48000)[1]
            freq=np.fft.rfftfreq(48000,1/48000)
            slow_fraction=float(motion_psd[freq<4].sum()/motion_psd.sum())
            r['trials'].append(dict(seed=seed,amount=amount,maximum_power_change_db=max_power,
                actual_delay_rms_microseconds=float(np.sqrt(np.mean(delay[24000:]**2))*1e6),
                delay_bound_microseconds=float(np.max(abs(delay))*1e6),motion_below4Hz_power_fraction=slow_fraction,
                band_changes=differences,raw_sha256=sha(a.out/f'raw_{seed}_{amount:g}.wav')))
            if seed==8121907:clip(f'common_phase_{amount:g}',candidate[crop])
            print(json.dumps(dict(seed=seed,amount=amount,mean_change_db=max_power,slow_phase_fraction=slow_fraction)),flush=True)
    page=['<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width">',
        '<title>主声线共同微扰 · V1</title><style>body{font:16px system-ui;max-width:800px;margin:36px auto;padding:0 20px;background:#f6f7f8}section{background:white;padding:20px;margin:16px 0;border-radius:12px}audio{width:100%}p{line-height:1.7}</style>',
        '<h1>主声线共同微扰 · V1</h1><p>回到认可的A移动尾排DNA＋相干低频。没有新增独立高频OSC云、噪声或高频增益。仅在1.2–1.9kHz过渡以上，对同一组原谐波加入共同、快速、有界的时间微扰；两声道共享，低谐波和独立低频保留。</p>',
        '<p>这是离线假设对照，未获听感认可。微扰不是实测曲轴抖动，尚未接实时系统。原版与两候选使用相同区间、DNA种子、增益0.5和首尾淡化，无逐条响度归一化。参考较短，不表示整段驾驶动作一致。</p>']
    for label,name in [('原始录音短参考','short_reference'),('认可原版：DNA＋相干低频','accepted_original'),('共同微扰：轻量','common_phase_0.5'),('共同微扰：中量','common_phase_1')]:
        page.append(f'<section><p>{html.escape(label)}</p><audio controls preload="none" src="{name}.wav"></audio></section>')
    page.append('<script>document.addEventListener("play",e=>{if(e.target.tagName==="AUDIO")document.querySelectorAll("audio").forEach(a=>{if(a!==e.target)a.pause()})},true)</script></html>')
    (a.out/'index.html').write_text('\n'.join(page),encoding='utf-8')
    r.update(result='offline_common_HF_phase_candidate_rendered',accepted_low_and_DNA_models_unchanged=True,
             old_CTests_not_repeated=True,device_checked=False,browser_interaction=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:(a.out/'report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(result=r['result'],source=r['source_phase_observation'],strength=r['strength_policy'])))

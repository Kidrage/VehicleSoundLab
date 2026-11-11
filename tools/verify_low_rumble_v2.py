"""C procedural LF rendering, unchanged DNA, bandwidth and no-loop evidence."""
from runtime_review import ROOT,sha
import json
import shutil
import subprocess
import numpy as np
import soundfile as sf
from scipy import signal

OUT=ROOT/'references/analysis/low_rumble_v2'
BUILD=ROOT/'build-sustain-monitor-v4/Release'
DNA=ROOT/'voices/dna_bank_v1/V10 Exterior.model'
BANK=ROOT/'voices/low_rumble_v2'


def render(model,path,seconds=8,pitch=1,amount=1,mode=0,stem=0):
    subprocess.run([str(BUILD/'low_rumble_probe.exe'),str(DNA),str(model),str(path),str(seconds),str(pitch),str(amount),str(mode),str(stem)],check=True,timeout=35)
    x,rate=sf.read(path,always_2d=True)
    assert rate==48000 and len(x)==round(seconds*rate) and np.isfinite(x).all()
    return x


def measure(x):
    f,p=signal.welch(x,48000,nperseg=65536,axis=0);p=p.mean(axis=1);df=f[1]-f[0]
    mask=(f>=25)&(f<=350);peak,_=signal.find_peaks(p)
    peak=sorted([i for i in peak if mask[i]],key=lambda i:p[i],reverse=True)[:3]
    tones=np.zeros(len(f),dtype=bool)
    for i in peak:tones|=abs(f-f[i])<2
    return dict(rms=float(np.sqrt(np.mean(x*x))),peak=float(abs(x).max()),
                bands_dbfs={f'{a}-{b}':float(10*np.log10(max(p[(f>=a)&(f<b)].sum()*df,1e-30))) for a,b in [(20,40),(40,80),(80,150),(150,250),(250,350)]},
                power_outside20_400=float(p[(f<20)|(f>400)].sum()/p.sum()),
                power_above1000=float(p[f>1000].sum()/p.sum()),
                top3_4hz_band_fraction=float(p[mask&tones].sum()/p[mask].sum()))


def audition(path,x):
    y=x.copy();y[-240:]*=np.linspace(1,0,240)[:,None];sf.write(path,y,48000,subtype='PCM_24')


def main():
    out=OUT/'renders';out.mkdir(exist_ok=False);checks=OUT/'checks';checks.mkdir()
    index=json.loads((BANK/'index.json').read_text(encoding='utf-8'));results={}
    reference,rate=sf.read(ROOT/'references/analysis/sound_dna_v1/renders/V10 Exterior_raw_float.wav',always_2d=True)
    previous,rate=sf.read(ROOT/'references/analysis/sustain_monitor_v3/baseline_device.wav',always_2d=True)
    for item in index['profiles']:
        name=item['name'];model=BANK/item['file'];assert sha(model)==item['model_sha256']
        low=render(model,out/f'{name}_low_raw.wav',seconds=16,stem=2)
        assert np.array_equal(low[:,0],low[:,1])
        stats=measure(low[4800:-4800]);assert stats['peak']<.9 and stats['power_above1000']<.0001
        assert stats['power_outside20_400']<.03 and stats['top3_4hz_band_fraction']<.5
        correlation=float(np.corrcoef(low[:384000,0],low[384000:,0])[0,1]);assert abs(correlation)<.1
        variants={}
        for amount in [0,.4,.6,.8,1]:
            tag=f'{amount*100:03.0f}';x=render(model,out/f'{name}_mix{tag}_float.wav',amount=amount)
            assert abs(x).max()<.95
            audition(out/f'{name}_mix{tag}_audition.wav',x)
            variants[tag]=dict(amount=amount,peak=float(abs(x).max()),sha256=sha(out/f'{name}_mix{tag}_float.wav'),audition_sha256=sha(out/f'{name}_mix{tag}_audition.wav'))
            if amount==0:assert np.array_equal(x,previous)
        raw=render(model,out/f'{name}_DNA_raw.wav',amount=1,stem=1)
        assert np.array_equal(raw,reference)
        solo=render(model,out/f'{name}_solo_float.wav',mode=2)
        audition(out/f'{name}_solo_audition.wav',solo)
        assert abs(solo[240:]-low[240:384000]*.5).max()<4e-8
        # Bounded pitch changes source pitch, not elapsed duration or texture time.
        for pitch in [.9,1.1]:render(model,out/f'{name}_pitch{pitch}.wav',seconds=2,pitch=pitch,amount=.6)
        results[name]=dict(model_sha256=sha(model),low_sha256=sha(out/f'{name}_low_raw.wav'),low_statistics=stats,
                           first_vs_second8s_correlation=correlation,variants=variants,
                           unchanged_DNA_sha256=sha(out/f'{name}_DNA_raw.wav'),solo_sha256=sha(out/f'{name}_solo_audition.wav'))
    # Preserve a direct same-DNA comparison against the earlier three-tone LF.
    old,rate=sf.read(ROOT/'references/analysis/low_body_v1/renders/bass100_body_float.wav',always_2d=True)
    audition(out/'old_three_tone_same_DNA.wav',previous+old)
    template=(BANK/'A Exterior.model').read_text();header,body=template.split('\n',1)
    bads={'truncated':header+'\n','nan':header.replace('0.035','nan')+'\n'+body,
          'trailing':template+'unexpected\n','count':template.replace('48000 192','48000 999999'),
          'frequency':template.replace('30.703125','3000'),'negative':header+'\n-1 '+body.split(' ',1)[1]}
    for name,text in bads.items():
        assert text!=template
        model=checks/f'{name}.model';model.write_text(text,encoding='ascii')
        output=checks/f'{name}.wav'
        run=subprocess.run([str(BUILD/'low_rumble_probe.exe'),str(DNA),str(model),str(output),'1','1','1','0','0'],timeout=10)
        assert run.returncode!=0 and not output.exists()
    model=checks/'低频模型.model';shutil.copy2(BANK/'A Exterior.model',model)
    x=render(model,checks/'中文低频.wav',seconds=1,stem=2)
    low,rate=sf.read(out/'A Exterior_low_raw.wav',always_2d=True);assert np.array_equal(x,low[:48000])
    result=dict(result='pass',profiles=results,previous_three_tone_statistics=measure(old),
                zero_rumble_exact_previous_monitor=True,DNA_raw_exact_all_profiles=True,
                invalid_models_rejected=True,unicode_model_export=True,new_stochastic_audio_not_loop=True,
                source_layer='One mono LF source; no LFE/room/stereo widening in this module.',
                audition_gain='Common0.5 headroom;5ms endpoints;no per-variant gain matching/EQ/compressor.',
                low_layer_subjective_acceptance=False,goal_complete=False,
                source_hashes={str(p.relative_to(ROOT)):sha(p) for folder in ['modules/low_rumble','experiments/sustain_monitor_v4'] for p in (ROOT/folder).iterdir() if p.is_file()},
                binaries={p.name:sha(p) for p in BUILD.glob('*.exe')})
    (OUT/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(result='pass',profiles={k:v['low_statistics'] for k,v in results.items()},old=result['previous_three_tone_statistics']),indent=2))


if __name__=='__main__':main()

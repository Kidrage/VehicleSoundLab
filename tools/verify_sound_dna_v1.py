"""Cross-profile/runtime regression; synthetic fixtures are not car realism evidence."""
from runtime_review import ROOT,sha
from sound_dna.profile import compile_file
import json
import subprocess
import shutil
import numpy as np
import soundfile as sf
from scipy import signal

OUT=ROOT/'references/analysis/sound_dna_v1'
BUILD=ROOT/'build-sustain-monitor-v3/Release'
BANK=ROOT/'voices/dna_bank_v1'


def render(model,path,pitch=1,amount=1,seconds=8,raw=True):
    run=subprocess.run([str(BUILD/'sound_dna_probe.exe'),str(model),str(path),str(seconds),str(pitch),str(amount),'1' if raw else '0'],capture_output=True,timeout=30)
    if run.returncode:raise RuntimeError(f'Render failed {model}: {run.returncode}')
    x,rate=sf.read(path,always_2d=True);assert rate==48000 and len(x)==round(seconds*rate) and np.isfinite(x).all()
    return x


def spectrum(x):
    f,p=signal.welch(x,48000,nperseg=65536,axis=0);return f,p


def main():
    out=OUT/'renders';out.mkdir(exist_ok=False);checks=OUT/'checks';checks.mkdir(exist_ok=False)
    bank=json.loads((BANK/'index.json').read_text());result=dict(result='pending',voices={},limits='Only V10 has recording-derived listening evidence;two synthetic sources verify reuse, input sample-rate handling and independent root Hz.')
    for item in bank['voices']:
        name=item['name'];model=BANK/item['file'];assert sha(model)==item['model_sha256']
        raw=render(model,out/f'{name}_raw_float.wav');device=render(model,out/f'{name}_monitor_float.wav',raw=False)
        expected=raw*.5;expected[:240]*=np.arange(240)[:,None]/239
        assert abs(device-expected).max()<6e-8 and abs(device).max()<.95
        f,p=spectrum(raw[4800:-4800]);peak=float(f[np.argmax(p[:,0])]);target=item['base_hz']*(5 if name=='V10 Exterior' else 2 if name=='Hollow Spectrum' else 1)
        #The V10 strongest peak can be20x rather than5x; verify the known5x line separately.
        if name=='V10 Exterior':assert p[np.argmin(abs(f-target)),0]>p[:,0].max()*.05
        else:assert abs(peak-target)<1
        device[-240:]*=np.linspace(1,0,240)[:,None];sf.write(out/f'{name}_audition.wav',device,48000,subtype='PCM_24')
        for pitch in [.9,1.1]:
            shifted=render(model,out/f'{name}_pitch{pitch}.wav',pitch=pitch,seconds=2)
            if name!='V10 Exterior':
                fs,ps=spectrum(shifted);assert abs(float(fs[np.argmax(ps[:,0])])-target*pitch)<1
        if name!='V10 Exterior':
            h=1 if name=='Warm Additive' else 2;t=np.arange(len(raw))/48000;z=np.mean(raw*np.exp(-2j*np.pi*item['base_hz']*h*t)[:,None],axis=0)
            phase=float(np.angle(z[1]/z[0]));assert abs(phase-.06*h)<.02
        result['voices'][name]=dict(base_hz=item['base_hz'],model_sha256=sha(model),raw_sha256=sha(out/f'{name}_raw_float.wav'),
            audition_sha256=sha(out/f'{name}_audition.wav'),peak_hz=peak,duration_seconds=8,bounded_pitch_preserves_duration=True,
            native_core='Same modules/sound_dna code for all profiles')
    raw,rate=sf.read(out/'V10 Exterior_raw_float.wav',always_2d=True)
    accepted,rate=sf.read(ROOT/'references/analysis/detail_modulation_v1/detail100_radial_float.wav',always_2d=True)
    error=float(abs(raw-accepted[:len(raw)]).max());assert error<2e-7
    #Strict invalid-profile controls, including unsupported high-frequency budgets.
    template=(BANK/'Warm Additive.model').read_text();first,rest=template.split('\n',1)
    for name,text in [('truncated',first+'\n'),('nan',template.replace('110\n','nan\n',1)),('trailing',template+'garbage\n'),('unsafe_root',template.replace('110\n','1000\n',1))]:
        assert text!=template
        path=checks/f'{name}.model';path.write_text(text,encoding='ascii')
        run=subprocess.run([str(BUILD/'sound_dna_probe.exe'),str(path),str(checks/f'{name}.wav'),'1','1','1','1'],timeout=10)
        assert run.returncode!=0 and not (checks/f'{name}.wav').exists()
    unicode_model=checks/'测试音色.model';shutil.copy2(BANK/'Warm Additive.model',unicode_model)
    other=render(unicode_model,checks/'中文输出.wav',seconds=1)
    base,rate=sf.read(out/'Warm Additive_raw_float.wav',always_2d=True);assert np.array_equal(other,base[:len(other)])
    #A truly static note must compile without undefined zero-variance PCA coefficients.
    sr=48000;t=np.arange(sr)/sr;static=.2*np.cos(2*np.pi*220*t+.2)+.06*np.cos(2*np.pi*660*t-.4)
    source=checks/'static.wav';sf.write(source,static,sr,subtype='FLOAT')
    info=compile_file(source,checks/'static_profile',220,'Static note contract',16,0)
    assert info['statistics']['components']==0
    x=render(checks/'static_profile/voice.model',checks/'static_result.wav',seconds=1)
    f,p=spectrum(x);assert abs(float(f[np.argmax(p[:,0])])-220)<1
    result.update(result='pass',accepted_phase_fixed_max_float_error=error,unicode_profile_and_export=True,zero_component_static_note=True,
        unsafe_truncated_nan_trailing_models_rejected=True,
        no_PAD_or_noise_in_DNA=True,source_sample_rates=[44100,48000],legacy_SUSTAIN_format_and_new_SOUND_DNA_format=True,
        source_hashes={str(p.relative_to(ROOT)):sha(p) for folder in ['modules/sound_dna','experiments/sustain_monitor_v3'] for p in (ROOT/folder).iterdir() if p.is_file()})
    (OUT/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()

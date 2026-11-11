"""Render fresh 8s procedural controls; waveform-error is not a realism metric."""
from runtime_review import ROOT,sha,rms
import json
import subprocess
import numpy as np
import soundfile as sf
from scipy import signal
from sustain_osc_v1.oracle import render

OUT=ROOT/'references/analysis/sustain_osc_v1'
BUILD=ROOT/'build-sustain-osc-v1/Release'


def summary(x,rate):
    f,p=signal.welch(x,rate,nperseg=8192,axis=0)
    return dict(rms_dbfs=rms(x),peak=float(abs(x).max()),
        bands_dbfs={f'{a}-{b}':float(10*np.log10(max(np.sum(p[(f>=a)&(f<b)])*(f[1]-f[0])/2,1e-30)))
                     for a,b in [(80,400),(400,1200),(1200,3000),(3000,8000),(8000,14000)]})


def main():
    out=OUT/'renders';out.mkdir(exist_ok=False)
    fit=json.loads((OUT/'fit.json').read_text(encoding='utf-8'))
    assert sha(OUT/'voice.model')==fit['model_sha256']
    result=dict(model_sha256=fit['model_sha256'],seed=48271,variants={},controls={},
        representation='Static statistical profile; no source PCM or time-indexed coefficient trajectory.',
        voice_subjectively_accepted=False)
    arrays={}
    for name,pitch,amount,seed,sweep in [('mean',1,0,48271,False),('generated',1,1,48271,False),
        ('other_seed',1,1,48272,False),('pitch_change',.9,1,48271,True)]:
        target=out/f'{name}_float.wav'
        cmd=[str(BUILD/'sustain_osc_probe.exe'),str(OUT/'voice.model'),str(target),'8',str(pitch),str(amount),str(seed)]
        if sweep:cmd.append('sweep')
        run=subprocess.run(cmd,check=True,capture_output=True,text=True,timeout=30)
        x,rate=sf.read(target,always_2d=True)
        assert rate==48000 and x.shape==(384000,2) and np.isfinite(x).all()
        arrays[name]=x
        result['variants'][name]=dict(frames=len(x),seconds=8,float_sha256=sha(target),statistics=summary(x[14400:-14400],rate),log=run.stdout.strip())
        if sweep:result['variants'][name]['pitch_schedule']=[[0,.9],[192000,1.1]]
        print(name,result['variants'][name]['statistics'],flush=True)
    arrays['reference'],rate=sf.read(OUT/'normalized_reference_float.wav',always_2d=True)
    result['reference_statistics']=summary(arrays['reference'][4800:-4800],rate)
    oracle=render(dict(np.load(OUT/'profile_arrays.npz')))
    error=float(abs(oracle-arrays['generated'][:len(oracle)]).max());assert error<2e-7
    assert not np.array_equal(arrays['generated'],arrays['other_seed'])
    assert not np.array_equal(arrays['generated'][:48000],arrays['generated'][6*48000:7*48000])
    result['controls']=dict(C_vs_independent_complex_sum_max_error=error,
        new_seed_changes_waveform=True,six_second_period_not_repeated=True,
        fixed_and_changed_pitch_both_eight_seconds=True)
    # Every item shares explicit headroom, never independent RMS matching.
    gain=.5*min(1,.85/(.5*max(float(abs(x).max()) for x in arrays.values())))
    result['audition']=dict(gain=gain,gain_db=float(20*np.log10(gain)),
        method='Shared fixed-6.0206dB headroom with common peak trim if required;5ms endpoint ramps;PCM24. No independent normalization/compressor/EQ boost.')
    for name,x in arrays.items():
        y=x*gain;ramp=240;y[:ramp]*=np.linspace(0,1,ramp)[:,None];y[-ramp:]*=np.linspace(1,0,ramp)[:,None]
        path=out/f'{name}_audition.wav';sf.write(path,y,rate,subtype='PCM_24')
        result.setdefault('audition_files',{})[name]=dict(file=path.name,sha256=sha(path),frames=len(y))
    for name,text in [('truncated',(OUT/'voice.model').read_text().splitlines()[0]+'\n'),
        ('invalid','VSL_SUSTAIN_OSC 1 48000 1024 256 99999 12\n')]:
        path=out/f'{name}.model';path.write_text(text,encoding='ascii')
        p=subprocess.run([str(BUILD/'sustain_osc_probe.exe'),str(path),str(out/f'{name}.wav'),'1','1','1','1'],capture_output=True,timeout=10)
        assert p.returncode!=0 and not (out/f'{name}.wav').exists()
        result['controls'][name]='rejected'
    result['ctest']=subprocess.run(['ctest','--test-dir',str(ROOT/'build-sustain-osc-v1'),'-C','Release','--output-on-failure'],
        check=True,capture_output=True,text=True,timeout=30).stdout
    result['binaries']={n:sha(BUILD/n) for n in ['sustain_osc_probe.exe','sustain_osc_checks.exe']}
    (out/'results.json').write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
    print('C oracle max error:',error,'common gain:',gain)


if __name__=='__main__':main()

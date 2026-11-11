"""Render the new additive low PAD without altering the accepted core."""
from runtime_review import ROOT,sha
import json
import subprocess
import numpy as np
import soundfile as sf
from scipy import signal

OUT=ROOT/'references/analysis/low_body_v1'


def main():
    out=OUT/'renders';out.mkdir(exist_ok=False)
    build=ROOT/'build-sustain-monitor-v2/Release';profile=ROOT/'references/analysis/sustain_osc_v1/voice.model'
    results={};arrays={}
    for name,amount in [('bass000',0),('bass050',.5),('bass100',1)]:
        subprocess.run([str(build/'low_body_probe.exe'),str(profile),str(OUT/'body.model'),str(out/name),'1',str(amount)],check=True,timeout=30)
        mix,r=sf.read(out/f'{name}_mix_float.wav',always_2d=True)
        body,s=sf.read(out/f'{name}_body_float.wav',always_2d=True)
        assert r==s==48000 and mix.shape==body.shape==(384000,2) and np.isfinite(mix).all() and abs(mix).max()<.9
        assert abs(body[:,0]-body[:,1]).max()<1e-7
        arrays[name]=mix
        audition=mix.copy();audition[-240:]*=np.linspace(1,0,240)[:,None]
        path=out/f'{name}_audition.wav';sf.write(path,audition,r,subtype='PCM_24')
        results[name]=dict(amount=amount,frames=len(mix),max_mix_peak=float(abs(mix).max()),
            body_rms_dbfs=float(10*np.log10(max(np.mean(body[2400:-2400]**2),1e-30))),
            mix_float_sha256=sha(out/f'{name}_mix_float.wav'),body_float_sha256=sha(out/f'{name}_body_float.wav'),
            audition_sha256=sha(path),processing='Same0.5 headroom and5ms onset/end ramps;no independent RMS normalization or compressor.')
        if amount==0:assert not body.any()
        else:
            f,p=signal.welch(body[2400:-2400,0],r,nperseg=65536)
            out_of_band=(f<20)|(f>180)
            results[name]['body_power_outside20_180_ratio']=float(p[out_of_band].sum()/p.sum())
            assert results[name]['body_power_outside20_180_ratio']<.001
            if amount==1:
                path=out/'body_solo_audition.wav';sf.write(path,body* np.r_[np.ones(len(body)-240),np.linspace(1,0,240)][:,None],r,subtype='PCM_24')
                results['solo']=dict(sha256=sha(path),gain='Actual layer gain, no solo boost')
    old,r=sf.read(ROOT/'references/analysis/sustain_monitor_v1/baseline_device.wav',always_2d=True)
    assert np.array_equal(arrays['bass000'],old)
    #Controls reject invalid/truncated low profiles without creating an output.
    for name,content in [('truncated','VSL_LOW_BODY 1 48000 3\n0 0\n'),('invalid','VSL_LOW_BODY 1 48000 3\nnan 0\n0 0\n0 0\n')]:
        bad=out/f'{name}.model';bad.write_text(content,encoding='ascii')
        p=subprocess.run([str(build/'low_body_probe.exe'),str(profile),str(bad),str(out/name),'1','1'],timeout=10)
        assert p.returncode!=0 and not (out/f'{name}_mix_float.wav').exists()
    record=dict(result='pass',variants=results,zero_body_exact_previous_native_output=True,
        unchanged_core_profile_sha256=sha(profile),low_profile_sha256=sha(OUT/'body.model'),
        no_new_PM_or_low_pitch_LFO=True,low_source_mono=True,subjective_low_layer_acceptance=False,
        source_hashes={str(p.relative_to(ROOT)):sha(p) for p in (ROOT/'experiments/low_body_v1').iterdir() if p.is_file()})
    (out/'results.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(record,ensure_ascii=False,indent=2))


if __name__=='__main__':main()

"""Independent kernel/quantization and preserved-runtime checks. No realism score."""
import json
import subprocess
from runtime_review import ROOT,sha,rms
import numpy as np
import soundfile as sf
from scipy.signal import fftconvolve
from scipy.integrate import quad

OUT=ROOT/'renders/firing_pulse_v1'
PROBE=ROOT/'build-experiment-firing-pulse/Release/firing_pulse_probe.exe'

def independent_kernel(rate,oversample):
    frames=rate//50
    t=(np.arange(frames*oversample)+1)/(rate*oversample)-.63/rate
    def pulse(tau):
        u=np.maximum(t/tau,0)
        return (np.e**2/16)*u**3*(4-u)*np.exp(-u)*(t>=0)*(u<=48)
    x=.65*pulse(.000075)+.35*pulse(.000028)
    count=24*oversample+1
    n=np.arange(count)-(count-1)/2
    fc=.38/oversample
    fir=2*fc*np.sinc(2*fc*n)*np.blackman(count)
    fir/=fir.sum()
    return fftconvolve(x,fir)[:len(x)][oversample-1::oversample]

def main():
    path=OUT/'independent_verification.json'
    if path.exists():raise SystemExit('Preserve finished verification.')
    result=json.loads((OUT/'results.json').read_text(encoding='utf-8'))
    kernel={}
    for sr in [16000,48000,192000]:
        target=OUT/f'kernel_{sr}.wav'
        subprocess.run([str(PROBE),'--kernel',str(target),str(sr)],check=True,cwd=ROOT)
        x,rate=sf.read(target,always_2d=True)
        predicted=independent_kernel(sr,4)
        error=float(abs(x[:,0]-predicted).max())
        assert rate==sr and np.all(x[:,1]==0) and error<3e-8
        fine=independent_kernel(sr,16)
        kernel[str(sr)]=dict(independent_analytic_FIR_max_error=error,
            oversampling4_vs16_relative_error_db=rms(predicted-fine)-rms(fine),
            note='Finite numerical convergence check, not a strict alias-free proof.')
    matches={}
    for name,case in result['cases'].items():
        if not case['auditions']:continue
        actual_rms=[]
        for tag,row in case['auditions'].items():
            raw,sr=sf.read(OUT/name/f'{tag}.wav',always_2d=True)
            left,right=[round(t*sr) for t in row['crop_seconds']]
            expected=raw[left:right].copy()
            ramp=.5-.5*np.cos(np.linspace(0,np.pi,240))
            expected[:240]*=ramp[:,None];expected[-240:]*=ramp[::-1,None]
            expected*=10**(row['gain_db']/20)
            a,rate=sf.read(OUT/name/row['file'],always_2d=True)
            assert rate==sr and a.shape==expected.shape and sf.info(OUT/name/row['file']).subtype=='PCM_24'
            assert abs(a).max()<=.850001 and float(abs(a-expected).max())<1.3e-7
            assert sha(OUT/name/row['file'])==row['sha256']
            actual_rms.append(rms(a))
        spread=max(actual_rms)-min(actual_rms);assert spread<.0001
        matches[name]=dict(max_RMS_difference_db=spread)
    frozen=ROOT/'baselines/app0.19.1'
    manifest=json.loads((frozen/'manifest.json').read_text(encoding='utf-8'))
    source_count=0;bin_count=0
    for item in manifest['files']:
        rel=item['path']
        if rel.startswith(('src/','tests/')) or rel in ['CMakeLists.txt','build.ps1','Launch-current.cmd','Launch-ui.cmd']:
            assert sha(ROOT/rel)==item['sha256'],rel
            source_count+=1
        if rel.startswith('bin/'):
            assert sha(frozen/rel)==item['sha256'],rel
            bin_count+=1
    prior=json.loads((ROOT/'renders/event_color_v1/results.json').read_text(encoding='utf-8'))
    ref='reference_A_exterior_blips.wav'
    assert sha(ROOT/'renders/event_color_v1'/ref)==prior['files'][ref]
    verification=dict(kernel=kernel,RMS_match=matches,preserved_native_sources_and_contracts=source_count,
        preserved_frozen_binary_files=bin_count,native_manifest_sha256=sha(frozen/'manifest.json'),
        reference_audition_sha256=sha(ROOT/'renders/event_color_v1'/ref),
        subjective_listening='Pending; tests do not establish timbre quality or target realism.')
    path.write_text(json.dumps(verification,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps(verification,ensure_ascii=False))

if __name__=='__main__':main()

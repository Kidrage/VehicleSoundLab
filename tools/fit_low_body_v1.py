"""Recording-informed low PAD shape with an explicit engineering gain.

Not an isolated physical source fit; do not add the original room/IR again.
"""
from runtime_review import ROOT,sha
from reference_segments import read_segment
import json
import numpy as np
import soundfile as sf
from scipy import signal

OUT=ROOT/'references/analysis/low_body_v1'


def bands(x,rate):
    f,p=signal.welch(x,rate,nperseg=16384,axis=0);p=p.mean(axis=1);df=f[1]-f[0]
    return {f'{a}-{b}':float(10*np.log10(max(p[(f>=a)&(f<b)].sum()*df,1e-30))) for a,b in [(20,40),(40,80),(80,150),(150,300),(300,1200)]}


def main():
    OUT.mkdir(exist_ok=False)
    x,rate,provenance=read_segment('A_exterior_moving','exterior_dynamic_observation')
    observations=np.load(ROOT/'references/analysis/sustain_osc_v1/ridge_observations.npz')
    seconds=observations['seconds'];ridge=observations['window128']
    source_t=np.arange(round(seconds[0]*rate),round(seconds[-1]*rate)+1)/rate
    f=np.interp(source_t,seconds,ridge)/5
    cycles=np.r_[0,np.cumsum((f[:-1]+f[1:])/(2*rate))]
    count=int(np.floor(cycles[-1]*1024));inverse=np.interp(np.arange(count)/1024,cycles,source_t)
    taps=signal.firwin(1025,14000,fs=rate,window=('kaiser',12))
    band=signal.fftconvolve(x,taps[:,None],mode='same',axes=0)
    dense=signal.resample_poly(band,16,1,axis=0,window=('kaiser',8.6),padtype='line')
    y=np.column_stack([np.interp(inverse*rate*16,np.arange(len(dense)),dense[:,c]) for c in range(2)])
    old,rr=sf.read(ROOT/'references/analysis/sustain_osc_v1/normalized_reference_float.wav',always_2d=True)
    assert rr==rate==48000 and y.shape==old.shape
    rows=[]
    for start in range(0,len(y)-1024+1,256):
        z=np.fft.rfft(y[start:start+1024],axis=0)[1:4]*2/1024
        z*=np.exp(-2j*np.pi*np.arange(1,4)*start/1024)[:,None];rows.append(z)
    rows=np.asarray(rows);mean=rows.mean(axis=(0,2))
    source_rms=float(np.sqrt(.5*np.sum(abs(mean)**2)))
    target_rms=.065;scale=target_rms/source_rms;weights=mean*scale
    assert abs(weights).max()<.25
    profile=OUT/'body.model'
    with profile.open('w',encoding='ascii',newline='\n') as file:
        file.write('VSL_LOW_BODY 1 48000 3\n')
        for z in weights:file.write(f'{z.real:.17g} {z.imag:.17g}\n')
    sf.write(OUT/'unhighpassed_normalized_float.wav',y,rate,subtype='FLOAT')
    result=dict(source=provenance,training_source_seconds=[316.10,317.25],
        source_coordinate='Same unproven ridge/5 relative cycle as sustain_osc_v1; not RPM or identified engine order.',
        derivative_processing='Same common time map/16x interpolation;14k lowpass only, no80Hz highpass. Raw stereo preserved separately.',
        raw_reference_bands_dbfs=bands(x[4800:61200],rate),old_normalized_bands_dbfs=bands(old,rate),unhighpassed_normalized_bands_dbfs=bands(y,rate),
        profile=dict(model_sha256=sha(profile),relative_harmonics=[1,2,3],default_frequencies_hz=[46.875,93.75,140.625],
            observed_mean_coefficients=[[float(z.real),float(z.imag)] for z in mean],
            stereo_projection='Explicit L/R complex-mean average for one mono low-body source; not engine banks or LFE.',
            raw_mean_rms=source_rms,engineering_full_amount_rms=target_rms,engineering_gain=scale,
            engineering_gain_db=float(20*np.log10(scale)),shape='Static mean low-harmonic amplitude/phase, no recording timeline or added PM.'),
        scope='An independently adjustable recording-informed low PAD/voicing supplement, not a measured separated structural/road/exhaust source or recovered microphone subbass.',
        limits=['Low-frequency source mixture cannot identify wind/road/engine independently','Existing harmonic1..3 contributions remain in the accepted core; new layer intentionally increases that band, not a decomposition','The80Hz filter weakened sub80 energy, but the raw exterior recording also has weak sub80; removing that filter alone cannot establish the requested thickness','No invented20Hz oscillator, room IR or LFE routing'],
        status='New low layer pending listening')
    (OUT/'fit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result['profile'],indent=2))


if __name__=='__main__':main()

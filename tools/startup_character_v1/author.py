"""Three coarse spectral states plus nine envelope controls; no PCM in model."""
from pathlib import Path
import hashlib,json
import numpy as np
from scipy import signal
import soundfile as sf

RATE=48000

def minimum_phase_shape(x,taps=8192):
    # Expected spectrum of fresh unit-variance excitation. Retain fine colour,
    # discard source phase; FIR is an excitation filter, not a room response.
    _,psd=signal.welch(x,fs=RATE,nperseg=min(4096,len(x)),noverlap=min(2048,len(x)//2),nfft=16384,detrend='constant')
    magnitude=np.sqrt(np.maximum(psd,np.max(psd)*1e-9))
    cep=np.fft.irfft(np.log(magnitude),n=16384)
    causal=np.zeros_like(cep);causal[0]=cep[0];causal[1:8192]=2*cep[1:8192];causal[8192]=cep[8192]
    h=np.fft.irfft(np.exp(np.fft.rfft(causal)),n=16384)[:taps]
    # Tail taper keeps a finite source memory without a hard truncation edge.
    h[-512:]*=np.linspace(1,0,512)
    h*=np.sqrt(np.mean(x*x))/max(1e-15,np.linalg.norm(h))
    return h

def write_profile(path,kernels):
    lines=['VSL_SPECTRAL_TEXTURE 1 48000 2 48000']
    for h,right in zip(kernels,(1.,-1.)):
        lines.append(f'{len(h)} {1/np.sqrt(2):.17g} {right:.17g}')
        lines.extend(' '.join(f'{v:.17g}' for v in h[n:n+8]) for n in range(0,len(h),8))
    path.write_text('\n'.join(lines)+'\n',encoding='ascii')

def author(source,output):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    with sf.SoundFile(source) as f:
        assert f.samplerate==RATE and f.channels==2
        f.seek(round(47.6*RATE));x=f.read(round(.58*RATE),dtype='float64')
    profiles=[]
    for i,part in enumerate(np.array_split(x,3)):
        mid=(part[:,0]+part[:,1])/np.sqrt(2);side=(part[:,0]-part[:,1])/np.sqrt(2)
        path=output/f'crank-{i}.sfir';write_profile(path,[minimum_phase_shape(mid),minimum_phase_shape(side)])
        profiles.append(dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    hop=480;window=1440
    times=np.arange(0,len(x)-window+1,hop);rms=np.array([np.sqrt(np.mean(x[n:n+window]**2)) for n in times])
    positions=(times+window/2)/len(x);knots=np.linspace(0,1,9)
    amp=np.interp(knots,positions,rms)
    # Spectral states already contain their own mean level; only normalized
    # coarse amplitude contour is retained here, with bounded fresh roughness.
    trend=np.interp(positions,knots,amp)
    roughness=float(np.clip(np.std(rms/np.maximum(trend,1e-12)-1)*1.5,.03,.30))
    amp/=np.mean(amp)
    info=dict(schema='vsl.startup-character/1',profiles=profiles,envelope=amp.tolist(),variation=roughness,
       source=str(source),source_sha256=hashlib.sha256(Path(source).read_bytes()).hexdigest(),seconds=[47.6,48.18],
       source_kind='Approved A exterior early acoustic action; not isolated starter motor or measured RPM',
       stages=3,phase='Source phase discarded; new random excitation; mid/side cross covariance omitted',
       role='Crank only. Catch uses same continuous engine DNA, no additive whole-engine catch template',
       room=False,pcm_playback=False,human_accepted=False)
    (output/'profile.json').write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding='utf-8')
    return info

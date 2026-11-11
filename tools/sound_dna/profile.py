"""Generic mono/stereo stable-pitch DNA compiler; no engine firing assumptions."""
import hashlib
import json
from pathlib import Path
from fractions import Fraction
import numpy as np
import soundfile as sf
from scipy import signal
from .statistics import factorize


def estimate(x,harmonics,components):
    if not 1<=harmonics<=320 or not 0<=components<=16:raise ValueError('Invalid model size')
    rows=[];k=np.arange(1,harmonics+1)
    for start in range(0,len(x)-1024+1,256):
        z=np.fft.rfft(x[start:start+1024],axis=0)[k]*2/1024*np.exp(-2j*np.pi*k*start/1024)[:,None]
        rows.append(np.column_stack([z[:,0].real,z[:,0].imag,z[:,1].real,z[:,1].imag]).ravel())
    return factorize(rows,harmonics,components)


def export(path,m,base_hz):
    h,k=m['basis'].shape[:2]
    with path.open('w',encoding='ascii',newline='\n') as f:
        f.write(f'VSL_SOUND_DNA 1 48000 1024 256 {h} {k} {base_hz:.17g}\n')
        f.write(' '.join(f'{v:.17g}' for v in m['rho'])+'\n')
        for i in range(h):
            row=np.r_[m['mean'][i],m['basis'][i].ravel(),m['residual_rho'][i],m['root'][i].ravel()]
            if not np.isfinite(row).all() or abs(row).max()>4:raise ValueError('Profile coefficients out of range')
            f.write(' '.join(f'{v:.17g}' for v in row)+'\n')


def compile_file(source,output,root_hz,name,harmonics=96,components=12):
    source=Path(source);output=Path(output)
    if not np.isfinite(root_hz) or not 5<=root_hz<=2000:raise ValueError('Explicit base/root Hz5..2000 required')
    if harmonics*root_hz*1.1>21600:raise ValueError('Harmonic count exceeds bounded-pitch frequency budget')
    x,rate=sf.read(source,always_2d=True)
    if x.shape[1] not in (1,2) or not np.isfinite(x).all() or len(x)<rate*.1:raise ValueError('Finite mono/stereo WAV required')
    mono=x.shape[1]==1
    if mono:x=np.repeat(x,2,axis=1)
    #Shared antialiased conversion to a1024-sample analysis cycle; the model
    #retains original root Hz for runtime, so playback does not stay at46.875Hz.
    ratio=Fraction(48000/float(rate)*root_hz/46.875).limit_denominator(10000)
    y=signal.resample_poly(x,ratio.numerator,ratio.denominator,axis=0,window=('kaiser',8.6))
    if not 16384<=len(y)<=48000*60:raise ValueError('Normalized training duration must be0.34..60s')
    model,stats=estimate(y,harmonics,components)
    output.mkdir(parents=True,exist_ok=False);export(output/'voice.model',model,root_hz)
    np.savez(output/'statistics.npz',**model)
    info=dict(schema='vsl.sound-dna-build/1',name=name,source=str(source.resolve()),source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        source_rate=rate,source_channels=1 if mono else 2,mono_policy='Explicit duplication to two observation channels' if mono else 'Preserved L/R',
        root_hz=root_hz,root_evidence='Caller-supplied acoustic pitch; never inferred physical RPM/cylinders',
        normalized_cycle_hz=46.875,resample_ratio=[ratio.numerator,ratio.denominator],normalized_frames=len(y),
        statistics=stats,model_sha256=hashlib.sha256((output/'voice.model').read_bytes()).hexdigest(),
        phase_policy='Fixed complex-mean phase; undefined mean uses zero phase',
        processing='Common resampling only;no filtering, normalization, compressor, PAD, noise or room',
        limits='Stable monophonic/quasiperiodic source. Inharmonic, polyphonic and time-varying-pitch material needs separate analysis; noise separation and physical source identification are not provided.')
    (output/'build.json').write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding='utf-8')
    return info

"""Explicit common-gain audition files shared by future versioned reviews."""
import numpy as np
import soundfile as sf
from runtime_review import sha,rms


def common_pair(out,arrays,tags,name):
    gain=min(10**((-23-max(map(rms,arrays)))/20),.85/max(float(abs(x).max()) for x in arrays))
    result={}
    for tag,x in zip(tags,arrays):
        file=out/f'audition_{name}_{tag}.wav';sf.write(file,x*gain,48000,subtype='PCM_24')
        result[tag]=dict(file=file.name,sha256=sha(file),channels=sf.info(file).channels,
            gain_db=float(20*np.log10(gain)),raw_rms_dbfs=rms(x),
            processing='One shared constant pair gain; louder full clip at -23 dBFS RMS, pair peak <=0.85. No separate normalization, compression or denoising.')
    return result

"""Sample-addressed original-media reads, with explicit provenance."""
import hashlib
from pathlib import Path
import numpy as np
import soundfile as sf


def sha(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk)
    return digest.hexdigest()


def read(path,start,stop):
    path=Path(path)
    with sf.SoundFile(path) as stream:
        sr=stream.samplerate;first=round(start*sr);last=round(stop*sr)
        if sr!=48000:raise ValueError('Authoring V1 requires an explicitly decoded 48 kHz master')
        if not 0<=first<last<=len(stream):raise ValueError('Source interval out of range')
        stream.seek(first);x=stream.read(last-first,dtype='float64',always_2d=True)
    if not np.all(np.isfinite(x)):raise ValueError('Nonfinite recording samples')
    return x,sr,dict(path=str(path.resolve()),sha256=sha(path),first_frame=first,last_frame=last,
        source_seconds=[first/sr,last/sr],channels=x.shape[1],sample_rate=sr,
        channel_policy='mean channel powers; no cancellation-prone stereo folding')

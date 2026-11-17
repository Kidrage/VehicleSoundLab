"""Immutable local imports and explicit 48 kHz decoding; no normalization."""
import base64
import math
from pathlib import Path
import subprocess
import numpy as np
import soundfile as sf
from scipy.signal import resample_poly
from event_authoring.audio import sha


def import_audio(repo,folder,data):
    raw=base64.b64decode(data['audio'],validate=True)
    if not 0<len(raw)<=48*1024**2:raise ValueError('导入音频需小于48 MB')
    suffix=Path(data.get('filename','reference.wav')).suffix.lower()
    if suffix not in ('.wav','.flac','.aif','.aiff','.mp3','.ogg','.m4a','.aac'):
        raise ValueError('请选择WAV、FLAC、AIFF、MP3、OGG或M4A音频')
    source=folder/('source'+suffix);source.write_bytes(raw)
    master=folder/'master.wav';policy='SoundFile decode; scipy resample_poly when needed; no gain change'
    try:info=sf.info(source)
    except RuntimeError:
        ffmpeg=Path('D:/repo/tools/ffmpeg/bin/ffmpeg.exe')
        if not ffmpeg.is_file():raise ValueError('此压缩格式需要本地ffmpeg；也可导入WAV')
        command=[str(ffmpeg),'-v','error','-i',str(source),'-t','61','-vn','-map_metadata','-1',
                 '-ar','48000','-acodec','pcm_f32le',str(master)]
        subprocess.run(command,capture_output=True,check=True,timeout=60,creationflags=0x08000000)
        info=sf.info(master);policy='ffmpeg decode/resample to FLOAT 48 kHz, native channels; no gain change'
    if info.channels not in (1,2) or not .12<=info.duration<=60:
        raise ValueError('请导入0.12–60秒的单声道或双声道片段，包含事件与附近背景')
    x,sr=sf.read(master if master.exists() else source,dtype='float64',always_2d=True)
    if not np.isfinite(x).all():raise ValueError('音频包含无效采样')
    if sr!=48000:
        factor=math.gcd(sr,48000);x=resample_poly(x,48000//factor,sr//factor,axis=0)
    sf.write(master,x,48000,subtype='FLOAT')
    sf.write(folder/'master-monitor.wav',x*.25,48000,subtype='FLOAT')
    edges=np.linspace(0,len(x),min(400,len(x))+1,dtype=int)
    waveform=[float(np.max(abs(x[a:b]))) for a,b in zip(edges[:-1],edges[1:])]
    return dict(filename=str(data.get('filename',source.name))[:180],original_sha256=sha(source),
        master_sha256=sha(master),sample_rate=48000,channels=x.shape[1],frames=len(x),
        duration=len(x)/48000,decode_policy=policy,waveform=waveform)


def ranges(data,duration):
    pairs=[]
    for key in ('seconds','background_seconds'):
        pair=data.get(key)
        if not isinstance(pair,list) or len(pair)!=2 or any(isinstance(v,bool) or not isinstance(v,(int,float)) for v in pair):
            raise ValueError('请填写事件和背景的起止秒数')
        minimum=.008 if key=='seconds' else .06
        if not np.isfinite(pair).all() or not 0<=pair[0]<pair[1]<=duration+1e-8 or round(pair[1]*48000)-round(pair[0]*48000)<round(minimum*48000):
            raise ValueError('事件选区至少0.008秒，背景至少0.06秒，且都需在音频内')
        pairs.append(pair)
    if pairs[0][1]-pairs[0][0]>5:raise ValueError('单次事件选区最长5秒')
    if max(pairs[0][0],pairs[1][0])<min(pairs[0][1],pairs[1][1]):
        raise ValueError('事件与背景选区不能重叠；请选择相邻的无事件背景')
    return pairs

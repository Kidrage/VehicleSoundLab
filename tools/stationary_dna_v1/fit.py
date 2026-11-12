"""Fit and C-render existing parameter-only DNA; does not alter runtime code."""
import subprocess
from fractions import Fraction
import numpy as np
from scipy import signal
import soundfile as sf
from drive_evidence_v1.sources import sha
from sound_dna.windowed import estimate
from sound_dna.profile import export


def fit(train, root, plan, out, probe):
    out.mkdir(parents=True,exist_ok=False)
    model, statistics = estimate(train,plan['harmonics'],plan['components'])
    model_path = out/'voice.model'
    export(model_path,model,root)
    np.savez_compressed(out/'statistics.npz',**model)
    result = dict(statistics=statistics,model_sha256=sha(model_path),
                  c_probe_sha256=sha(probe),rendered={})
    for label,pitch,amount in [('mean',1,0),('detail',1,1),('lower',.9,1),('higher',1.1,1)]:
        wav = out/f'{label}.wav'
        command = [str(probe),str(model_path),str(wav),'20',str(pitch),str(amount),'1']
        process = subprocess.run(command,capture_output=True,text=True,check=False)
        (out/f'{label}_command.txt').write_text(subprocess.list2cmdline(command)+'\n'+process.stdout+process.stderr,encoding='utf-8')
        if process.returncode:
            raise RuntimeError(f'C probe returned {process.returncode}: {label}')
        audio,rate=sf.read(wav,always_2d=True)
        assert rate==48000 and audio.shape==(960000,2) and np.isfinite(audio).all()
        result['rendered'][label]=dict(sha256=sha(wav),peak=float(abs(audio).max()),
            rms_LR=np.sqrt(np.mean(audio*audio,axis=0)).tolist(),pitch=pitch,amount=amount,
            frames=len(audio))
    return result


def normalized_playback(audio,root):
    ratio=Fraction(root/46.875).limit_denominator(10000)
    return signal.resample_poly(audio,ratio.numerator,ratio.denominator,axis=0,window=('kaiser',8.6))


def physical_playback(audio,root):
    ratio=Fraction(46.875/root).limit_denominator(10000)
    return signal.resample_poly(audio,ratio.numerator,ratio.denominator,axis=0,window=('kaiser',8.6))

"""Export/verify a coefficient-only C diagnostic without overwriting assets."""
from runtime_review import sha
import subprocess
import numpy as np
import soundfile as sf
from osc_quality_v1.metrics import relative_error
from .bank import fit,render,export


def variant(probe, out, x, rate, name, limit):
    model=out/f'{name}.model'
    target=out/f'{name}_c_float.wav'
    audition=out/f'{name}_audition.wav'
    if any(p.exists() for p in (model,target,audition)):
        raise FileExistsError('Preserve existing diagnostic coefficients and audio')
    grains=fit(x,limit=limit)
    python=render(grains,len(x))
    export(model,grains,rate,len(x))
    process=subprocess.run([str(probe),str(model),str(target)],capture_output=True,text=True,check=True,timeout=120)
    c,sr=sf.read(target,always_2d=True)
    assert sr==rate and c.shape==(len(x),2) and np.array_equal(c[:,0],c[:,1])
    error=float(abs(c[:,0]-python).max());assert error<1e-7
    sf.write(audition,c[:,0],rate,subtype='PCM_24')
    if limit is None:assert np.max(abs(python-x))<1e-12
    return dict(oscillators_per_grain=len(grains[0][1]),max_overlapping_grains=4,
        window=512,hop=128,residual_db=relative_error(x,c[:,0],rate),C_python_error=error,
        peak=float(abs(c).max()),audition_sha256=sha(audition),model_sha256=sha(model),log=process.stdout.strip(),
        note='All complex coefficients for full transform' if limit is None else f'Strongest{limit} Fourier bins per grain, no peak tracking')

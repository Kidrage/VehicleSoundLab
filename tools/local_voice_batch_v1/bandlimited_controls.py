"""Known C/independent PRNG/direct-sum check before any new recording is read."""
import subprocess
import numpy as np
import soundfile as sf
from sound_dna.profile import export
from .audit_kernels import seeded_samples
from research_archive_v1 import sha


def float_error(actual, expected):
    error=np.abs(actual-expected)
    # Per-value FLOAT quantization plus separately declared double-render bound.
    tolerance=.5001*np.spacing(np.abs(expected.astype('float32'))).astype(float)+2e-10
    if not np.all(error<=tolerance):
        raise AssertionError(('FLOAT/analytic mismatch',float(error.max()),float((error-tolerance).max())))
    return dict(maximum_error_FS=float(error.max()),maximum_excess_FS=float((error-tolerance).max()),
                bound='0.5001 local FLOAT ULP +2e-10FS double phase/sum allowance')


def run(folder,probe,repo):
    folder.mkdir(exist_ok=False)
    h,k=288,12
    model=dict(mean=np.zeros((h,4)),basis=np.zeros((h,k,4)),rho=np.linspace(-.4,.6,k),
               residual_rho=np.full(h,.3),root=np.zeros((h,4,4)))
    for order,amp in ((3,.12),(220,.06),(288,.04)):
        i=order-1
        model['mean'][i]=[amp*np.cos(.2),amp*np.sin(.2),amp*.7*np.cos(-.4),amp*.7*np.sin(-.4)]
        model['basis'][i,0,0]=.001;model['basis'][i,4,3]=.0007
        model['root'][i]=np.diag([.0002,.0001,.00015,.0001])
    export(folder/'known.model',model,90)
    results=[];indices=[0,1,37,239,240,1000,4000,7999,12000,16000,20000,23999]
    for seed in (23117,61927):
        dest=folder/('known_%d.wav'%seed)
        argv=list(map(str,[probe,folder/'known.model',dest,.5,90,1,seed,37]))
        done=subprocess.run(argv,cwd=repo,capture_output=True,timeout=120)
        (folder/('known_%d.log'%seed)).write_bytes(done.stdout+done.stderr)
        assert done.returncode==0
        actual,rate=sf.read(dest,always_2d=True)
        assert rate==48000 and actual.shape==(24000,2)
        expected=seeded_samples(model,90,seed,indices,bandlimited=True)
        results.append(dict(seed=seed,indices=indices,argv=argv,sha256=sha(dest),
                            **float_error(actual[indices],expected)))
    return dict(result='known_bandlimited_PRNG_and_stereo_C_passed',cases=results,
                all288_state_draws=True,static_taper='19200..21600Hz carrier only',new_source_read=False)

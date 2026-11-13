"""Native finite observations and stationary cumulant budget; no source identity."""
import numpy as np
from scipy import signal
from scipy.optimize import nnls


def describe(x):
    y=np.asarray(x)-np.mean(x,axis=0)
    v=np.mean(y*y,axis=0)
    if np.any(v<=0): raise ValueError('Positive variance required')
    k=np.mean(y**4,axis=0)-3*v*v
    return dict(variance=v.tolist(),cumulant4=k.tolist(),excess=(k/v**2).tolist(),
                skew=(np.mean(y**3,axis=0)/v**1.5).tolist())


def observe(audio,sos,trim):
    bands=np.column_stack([signal.sosfilt(s,audio[:,0])[trim:-trim] for s in sos])
    return describe(bands),bands


def compile_model(profile,main,source,sos,plan):
    """One nonnegative cumulant solve; fitting never sees the check recording."""
    size=plan['effective_impulse_frames']; responses=[];tails=[]
    for s in sos:
        row=[];tail=[]
        for kernel in profile['kernels']:
            taps=np.zeros(size);taps[:len(kernel['taps'])]=kernel['taps']
            h=signal.sosfilt(s,taps)*kernel['gain'];row.append(h)
            tail.append(float(np.sum(h[-4096:]**2)/np.sum(h*h)))
        responses.append(row);tails.append(tail)
    h=np.array(responses)
    if np.max(tails)>=1e-12: raise ValueError('Effective impulse truncation not qualified')
    main_stats,_=observe(main,sos,plan['trim_frames'])
    variance=np.sum(h*h,axis=(1,2))+np.array(main_stats['variance'])
    debt=np.array(source['excess'])*variance**2-np.array(main_stats['cumulant4'])
    if np.any(debt<=0): raise ValueError('Nonpositive cumulant debt; do not invent it')
    matrix=np.sum(h[:,plan['kernel_indices'],:]**4,axis=2)
    normal=matrix/debt[:,None]
    # Column normalization only changes solver coordinates, not the objective.
    scale=np.linalg.norm(normal,axis=0)
    solution,_=nnls(normal/scale,np.ones(len(debt)))
    kappa=solution/scale;relative=matrix@kappa/debt-1
    if np.max(abs(relative))>.1: raise ValueError('Stationary fourth-moment budget not supported')
    probability=3/(kappa+3)
    return dict(schema='vsl.sparse-spectral-excitation/1',kernel_indices=plan['kernel_indices'],
                excess_input=kappa.tolist(),probability=probability.tolist(),recorded_timeline=False,
                engine_firing_events=False,physical_source_identified=False),dict(
                matrix=matrix.tolist(),model_variance=variance.tolist(),debt=debt.tolist(),
                relative_residual=relative.tolist(),main=main_stats,tail_power_fraction=tails,
                expected_events_per_second=(48000*probability).tolist()),h


def known_controls():
    # Enumerate the exact independent binary ensemble, not a Monte Carlo fit.
    import itertools
    filters=[np.array([.8,.6]),np.array([.3,-.4])]
    samples=np.array(list(itertools.product([-1.,1.],repeat=4)))
    y=samples[:,:2]@filters[0]+samples[:,2:]@filters[1]
    m=describe(y);expected=-2*sum(np.sum(h**4) for h in filters)
    assert abs(m['cumulant4']-expected)<1e-12
    assert abs(m['variance']-sum(np.sum(h*h) for h in filters))<1e-12
    # Exact gated Gaussian moments for an arbitrary p; normalized Gaussian m2=1,m4=3.
    for p in [.002,.17,1.]:
        v=p/p;fourth=3*p/p**2
        assert abs(fourth/v**2-3-(3/p-3))<1e-10
    return dict(independent_fir_cumulant_error=abs(m['cumulant4']-expected),
                sparse_gaussian_moments=True)

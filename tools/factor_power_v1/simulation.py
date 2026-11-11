"""Independent companion simulation and lfilter reconstruction of known controls."""
import numpy as np
from scipy import signal
from .moments import interval_energy,interpolate_variance


def ensemble(profiles,weights,steps,replicates,seed,quadrature_order):
    rng=np.random.default_rng(seed)
    history=np.zeros((replicates,len(profiles),len(profiles[0]['coefficients'])))
    for k,p in enumerate(profiles):
        history[:,k,:]=rng.normal(size=(replicates,len(p['coefficients'])))@np.linalg.cholesky(p['covariance']).T
    coefficients=np.array([p['coefficients'] for p in profiles])
    gain=np.sqrt([p['innovation_variance'] for p in profiles]);total=np.zeros((replicates,len(weights)))
    for i in range(steps):
        left=history[:,:,0].copy()
        right=np.einsum('rkp,kp->rk',history,coefficients)+rng.normal(size=left.shape)*gain
        total+=interval_energy(left,right,profiles,weights,quadrature_order)
        history[:,:,1:]=history[:,:,:-1]
        history[:,:,0]=right
    return total/steps


def reconstruct(profiles,weights,plan,seed):
    frames=round(plan['duration_seconds']*plan['sample_rate']);steps=frames//plan['update_frames']
    # The old host consumes2 factor draws and200 unused residual draws/update.
    # Shape-independent NumPy draws preserve that original stream exactly.
    innovations=np.random.default_rng(seed).normal(size=(steps+1,202))
    initial_rng=np.random.default_rng(seed^0x589a712d)
    factors=np.empty((steps+1,len(profiles)));factors[0]=innovations[0,:2]
    for k,p in enumerate(profiles):
        history=np.r_[factors[0,k],p['covariance'][1:,0]*factors[0,k]+
            p['conditional_cholesky']@initial_rng.normal(size=len(p['coefficients'])-1)]
        denominator=np.r_[1.,-p['coefficients']];numerator=np.array([np.sqrt(p['innovation_variance'])])
        state=signal.lfiltic(numerator,denominator,history)
        factors[1:,k],_=signal.lfilter(numerator,denominator,innovations[1:,k],zi=state)
    u=np.arange(plan['update_frames'])/plan['update_frames']
    variance=interpolate_variance(profiles,u)@(weights*weights).T
    z=((1-u)[None,:,None]*factors[:-1,None,:]+u[None,:,None]*factors[1:,None,:])@weights.T
    normalized_amplitude=np.exp(z-variance[None,:,:]).reshape(frames,-1)
    energy=np.mean(normalized_amplitude**2,axis=0)
    index=np.arange(frames);harmonics=np.array(plan['active_harmonic_indices'])+1
    angles=2*np.pi*index[:,None]*harmonics[None,:]/1024
    audio=np.column_stack([np.sum(normalized_amplitude*plan['carrier_amplitudes_LR'][channel]*
        np.cos(angles+(plan['right_phase'] if channel else 0)),axis=1) for channel in range(2)])
    return audio,energy,factors

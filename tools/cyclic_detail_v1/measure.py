"""Cycle-mean decomposition and held-out residual-power dependence, no source identity."""
import numpy as np
from scipy import signal

def split(audio,cycle):
    count=len(audio)//cycle
    if count<8:raise ValueError('At least eight complete observed cycles required')
    blocks=audio[:count*cycle].reshape(count,cycle,2)
    mean=blocks.mean(axis=0)
    coherent=np.tile(mean,(count,1))
    residual=blocks.reshape(-1,2)-coherent
    return coherent,residual,dict(complete_cycles=count,discarded_tail_frames=len(audio)-count*cycle,
        coherent_power=np.mean(coherent**2,axis=0).tolist(),residual_power=np.mean(residual**2,axis=0).tolist(),
        orthogonality=np.mean(coherent*residual,axis=0).tolist(),
        scope='Finite ensemble mean; coherent stationary noise bias is nonzero. Not physical source separation.')

def dependence(audio,root,bands,plan):
    cycle=plan['cycle_frames'];trim=plan['trim_cycles'];count=len(audio)//cycle
    if count-2*trim<6:raise ValueError('Insufficient complete interior cycles')
    rows=[];features=[]
    theta=2*np.pi*np.arange(cycle)/cycle
    carrier=np.exp(-1j*np.arange(1,plan['harmonics']+1)[:,None]*theta[None,:])
    for lo,hi in bands:
        # Canonical analysis cycle is1024frames, while bands are native acoustic Hz.
        scale=(48000/cycle)/root
        sos=signal.butter(plan['filter_order'],[lo*scale,hi*scale],fs=48000,btype='bandpass',output='sos')
        filtered=signal.sosfiltfilt(sos,audio,axis=0)
        cycles=filtered[:count*cycle].reshape(count,cycle,2)[trim:count-trim]
        power=cycles**2
        level=np.mean(power,axis=(0,1))
        beta=2*np.einsum('nsc,ks->nck',power,carrier)/cycle
        beta/=np.maximum(level,plan['minimum_energy_FS2'])[None,:,None]
        if max(level)<plan['minimum_energy_FS2']:beta[:]=0
        features.append(beta)
        rows.append(dict(band_hz=[lo,hi],interior_cycles=len(cycles),power_LR=level.tolist()))
    features=np.array(features)
    def score(values):
        first=values[:,::2].mean(axis=1);second=values[:,1::2].mean(axis=1)
        return np.real(first*second.conj()).mean(axis=(1,2))
    observed=score(features);rng=np.random.default_rng(plan['seed']);null=[]
    orders=np.arange(1,plan['harmonics']+1)
    for _ in range(plan['permutations']):
        # One shift per cycle, common to channels and bands; preserves within-cycle L/R.
        phase=rng.uniform(0,2*np.pi,features.shape[1])
        changed=features*np.exp(-1j*phase[:,None]*orders[None,:])[None,:,None,:]
        null.append(float(max(score(changed))))
    null=np.array(null)
    for i,row in enumerate(rows):
        prob=(1+int(np.sum(null>=observed[i])))/(len(null)+1)
        row.update(train_heldout_cross_statistic=float(observed[i]),familywise_p=prob,
            periodic_residual_power_supported=bool(observed[i]>0 and prob<=plan['familywise_p']))
    return dict(bands=rows,max_null=null.tolist(),
        caution='Short correlated cycles and source conditioning limit permutation exchangeability; descriptive evidence only, not physical combustion or modulation-law qualification.')

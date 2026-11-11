"""Static harmonic mean plus correlated stochastic complex modulation.

The profile contains no time-indexed coefficient trajectory. All fitted arrays
are summary moments, principal directions and AR1 correlations.
"""
import numpy as np


def estimate(audio,window=1024,hop=256,harmonics=300,components=12):
    k=np.arange(1,harmonics+1)
    rows=[]
    for start in range(0,len(audio)-window+1,hop):
        z=np.fft.rfft(audio[start:start+window],axis=0)[k]*2/window
        z*=np.exp(-2j*np.pi*k*start/window)[:,None]
        rows.append(np.column_stack([z[:,0].real,z[:,0].imag,z[:,1].real,z[:,1].imag]).ravel())
    x=np.asarray(rows);mean=x.mean(axis=0);centered=x-mean
    u,s,v=np.linalg.svd(centered,full_matrices=False)
    kcount=min(components,len(s)-1)
    basis=v[:kcount]*(s[:kcount,None]/np.sqrt(len(x)-1))
    scores=u[:,:kcount]*np.sqrt(len(x)-1)
    rho=np.clip(np.sum(scores[1:]*scores[:-1],axis=0)/np.sum(scores[:-1]**2,axis=0),-.95,.95)
    residual=(centered-scores@basis).reshape(-1,harmonics,4)
    root=[];rhos=[]
    for h in range(harmonics):
        r=residual[:,h,:]
        covariance=r.T@r/(len(r)-1)
        eigen,vec=np.linalg.eigh(covariance)
        root.append(vec@np.diag(np.sqrt(np.maximum(eigen,0))))
        rhos.append(float(np.clip(np.sum(r[1:]*r[:-1])/max(np.sum(r[:-1]**2),1e-30),-.95,.95)))
    model=dict(mean=mean.reshape(harmonics,4),basis=basis.reshape(kcount,harmonics,4).transpose(1,0,2),
        rho=rho,root=np.asarray(root),residual_rho=np.asarray(rhos))
    stats=dict(observation_frames=len(x),window=window,hop=hop,harmonics=harmonics,components=kcount,
        PCA_variance_fraction=float(np.sum(s[:kcount]**2)/np.sum(s*s)),
        scope='Descriptive complex-coefficient moments; variance fraction is not realism or physical-source fraction.',
        coherence_fraction=float(np.sum(mean*mean)/max(np.mean(np.sum(x*x,axis=1)),1e-30)),
        rho_range=[float(rho.min()),float(rho.max())],
        residual_rho_range=[float(np.min(rhos)),float(np.max(rhos))],
        source_trajectory_stored=False)
    return model,stats


def export(path,model,rate=48000,window=1024,hop=256):
    h,k=model['basis'].shape[:2]
    with path.open('w',encoding='ascii',newline='\n') as f:
        f.write(f'VSL_SUSTAIN_OSC 1 {rate} {window} {hop} {h} {k}\n')
        f.write(' '.join(f'{v:.17g}' for v in model['rho'])+'\n')
        for i in range(h):
            values=np.r_[model['mean'][i],model['basis'][i].ravel(),model['residual_rho'][i],model['root'][i].ravel()]
            f.write(' '.join(f'{v:.17g}' for v in values)+'\n')

"""Shared complex-coefficient statistics; no window or source assumptions."""
import numpy as np


def factorize(rows, harmonics, components):
    a=np.asarray(rows);mean=a.mean(axis=0);centered=a-mean
    u,s,v=np.linalg.svd(centered,full_matrices=False)
    rank=int(np.sum(s>max(float(s[0])*1e-7,1e-12))) if len(s) else 0
    count=min(components,rank,len(a)-1)
    basis=v[:count]*(s[:count,None]/np.sqrt(len(a)-1));scores=u[:,:count]*np.sqrt(len(a)-1)
    den=np.sum(scores[:-1]**2,axis=0)
    rho=np.clip(np.divide(np.sum(scores[1:]*scores[:-1],axis=0),den,out=np.zeros(count),where=den>1e-30),-.95,.95)
    residual=(centered-scores@basis).reshape(-1,harmonics,4);roots=[];rhos=[]
    for h in range(harmonics):
        r=residual[:,h];cov=r.T@r/(len(r)-1);e,w=np.linalg.eigh(cov)
        roots.append(w@np.diag(np.sqrt(np.maximum(e,0))))
        rhos.append(float(np.clip(np.sum(r[1:]*r[:-1])/max(np.sum(r[:-1]**2),1e-30),-.95,.95)))
    model=dict(mean=mean.reshape(harmonics,4),basis=basis.reshape(count,harmonics,4).transpose(1,0,2),rho=rho,root=np.array(roots),residual_rho=np.array(rhos))
    return model,dict(observation_frames=len(a),rank=rank,components=count,harmonics=harmonics)

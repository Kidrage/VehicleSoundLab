"""Generic existing SOUND_DNA parameter import and explicit-frequency scaling."""
import numpy as np

def load(path):
    lines=path.read_text(encoding='ascii').splitlines();head=lines[0].split()
    assert head[:5]==['VSL_SOUND_DNA','1','48000','1024','256']
    h,k=map(int,head[5:7]);root=float(head[7])
    rows=np.array([[float(v) for v in row.split()] for row in lines[2:]])
    assert rows.shape==(h,4+4*k+1+16)
    return dict(mean=rows[:,:4],basis=rows[:,4:4+4*k].reshape(h,k,4),
        rho=np.array([float(v) for v in lines[1].split()]),residual_rho=rows[:,4+4*k],
        root=rows[:,-16:].reshape(h,4,4)),root

def attenuate(model,root,amount,transition):
    hz=root*np.arange(1,len(model['mean'])+1)
    u=np.clip((hz-transition[0])/(transition[1]-transition[0]),0,1)
    gain=np.sqrt(1-amount*u*u*(3-2*u))
    result={k:v.copy() for k,v in model.items()}
    for name in ('mean','basis','root'):
        result[name]*=gain.reshape((len(gain),)+(1,)*(result[name].ndim-1))
        assert np.array_equal(result[name][hz<=transition[0]],model[name][hz<=transition[0]])
    for name in ('rho','residual_rho'):assert np.array_equal(result[name],model[name])
    return result,gain

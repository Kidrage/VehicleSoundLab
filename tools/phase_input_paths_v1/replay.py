"""All frozen conditional maps, with one declared P/uniform anchor pair."""
import numpy as np
from scipy.special import ndtr
from radial_copula_v1.latent import features
from radial_copula_v1.quantiles import lookup
from carrier_transfer_v1.groups import indices
from .factor import phases


def fields(bundle,capture,frames,block):
    model={k[6:]:v for k,v in bundle.items() if k.startswith('model_')};h=len(model['fixed_phase'])
    amplitude=np.empty((frames,h,2));common=np.empty((frames,h));uniform=np.empty_like(common)
    for first in range(0,frames,block):
        n=np.arange(first,min(first+block,frames));u=(n%256)/256
        normal=features(model,capture['state'],n//256,u)
        extra=features(model,capture['independent_state'],n//256,u)
        amplitude[n]=lookup(model['amplitude'],normal[:,:2*h]).reshape(-1,h,2)
        common[n]=lookup(model['phase'][:,:h],normal[:,2*h:3*h])
        uniform[n]=ndtr(extra[:,3*h:])
    return amplitude,common,uniform


def generate(bundle,amplitude,common,uniform,root,edges,decoders):
    frames,h,_=amplitude.shape;n=np.arange(frames)
    tags=indices(h,root,edges);x=np.clip((np.arange(1,h+1)*root-19200)/2400,0,1)
    taper=1-3*x*x+2*x*x*x;outputs={};diagnostics={}
    for name in decoders:
        group=np.zeros((frames,4,len(edges)-1,2));steps=np.empty((h,4));interaction=np.empty((h,2))
        for j in range(h):
            product=amplitude[:,j,0]*amplitude[:,j,1]/bundle['mean_product'][j]
            delta=phases(product,uniform[:,j],bundle['knots'][j],bundle[name][j],bundle['low'][j],bundle['high'][j])
            steps[j]=abs(np.diff(delta,axis=0)).max(axis=0)
            phi=delta[:,3]-delta[:,1]-delta[:,2]+delta[:,0]
            interaction[j]=[np.sqrt(np.mean(phi*phi)),abs(phi).max()]
            carrier=(2*np.pi*(n%1024)/1024*(j+1))[:,None]
            for c,sign in ((0,1),(1,-1)):
                angle=common[:,j,None]+sign*delta/2
                group[:,:,tags[j],c]+=amplitude[:,j,None,c]*taper[j]*np.cos(carrier+angle)
        outputs[name]=group;diagnostics[name]=dict(maximum_phase_step=steps,phase_interaction_RMS_max=interaction)
    return outputs,diagnostics

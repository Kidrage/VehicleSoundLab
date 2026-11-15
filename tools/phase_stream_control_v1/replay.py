"""Original amplitude/common phase; only relative phase uses saved extra stream."""
import numpy as np
from radial_copula_v1.latent import features
from radial_copula_v1.quantiles import lookup
from carrier_transfer_v1.groups import indices


def generate(bundle, capture, root, edges, frames, block):
    model={key[6:]:v for key,v in bundle.items() if key.startswith('model_')}
    h=len(model['fixed_phase']);orders=np.arange(1,h+1)
    tags=indices(h,root,edges)
    grouped=np.empty((frames,len(edges)-1,2))
    x=np.clip((orders*root-19200)/2400,0,1);taper=1-3*x*x+2*x*x*x
    probes=capture['probe_positions'];probe_fields={key:np.empty((len(probes),h,2) if key=='amplitude' else (len(probes),h)) for key in ('amplitude','common','relative')}
    original_error=0.;partition_error=0.
    maxima={key:np.zeros(h) for key in ('original_relative','independent_relative')}
    previous={key:None for key in maxima}
    for first in range(0,frames,block):
        n=np.arange(first,min(first+block,frames));fraction=(n%256)/256
        normal=features(model,capture['state'],n//256,fraction)
        extra=features(model,capture['independent_state'],n//256,fraction)
        amplitude=lookup(model['amplitude'],normal[:,:2*h]).reshape(-1,h,2)
        common=lookup(model['phase'][:,:h],normal[:,2*h:3*h])
        original=lookup(model['phase'][:,h:],normal[:,3*h:])
        independent=lookup(model['phase'][:,h:],extra[:,3*h:])
        for key,delta in (('original_relative',original),('independent_relative',independent)):
            track=np.vstack([previous[key],delta]) if previous[key] is not None else delta
            if len(track)>1:maxima[key]=np.maximum(maxima[key],abs(np.diff(track,axis=0)).max(axis=0))
            previous[key]=delta[-1:]
        mask=(probes>=first)&(probes<first+len(n));at=probes[mask]-first
        probe_fields['amplitude'][mask]=amplitude[at]
        probe_fields['common'][mask]=common[at]
        probe_fields['relative'][mask]=independent[at]
        angle=np.stack([common+independent/2,common-independent/2],axis=-1)
        carrier=(2*np.pi*(n%1024)/1024)[:,None,None]*orders[None,:,None]
        partials=amplitude*taper[None,:,None]*np.cos(carrier+angle)
        for group in range(len(edges)-1):grouped[n,group]=partials[:,tags==group].sum(axis=1)
        partition_error=max(partition_error,float(abs(partials.sum(axis=1)-grouped[n].sum(axis=1)).max()))
        if mask.any():
            old_angle=np.stack([common[at]+original[at]/2,common[at]-original[at]/2],axis=-1)
            old=(amplitude[at]*taper[None,:,None]*np.cos(carrier[at]+old_angle)).sum(axis=1)
            original_error=max(original_error,float(abs(old-capture['relative_audio'][probes[mask]]).max()))
    return grouped,dict(**{key+'_max_step':v for key,v in maxima.items()},
        **{'probe_'+key:v for key,v in probe_fields.items()}),original_error,partition_error

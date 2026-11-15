"""Same-window inverse diagnostics; these are in-sample fits, not new voices."""
import numpy as np
from conditional_phase_time_v1.observer import analyze,power_statistics
from carrier_transfer_v1.spectral import measure,summary
from carrier_transfer_v1.groups import indices


def interpolate_rows(observer,coefficients):
    centers=observer.starts+2048;flat=coefficients.reshape(len(coefficients),-1)
    nodes=np.stack([np.interp(observer.positions,centers,z.real)+1j*np.interp(observer.positions,centers,z.imag) for z in flat.T],axis=1)
    return nodes.reshape(observer.shape)


def capture(observer,nodes,root,bands,edges,source_audio,target):
    tags=indices(len(observer.orders),root,edges)
    grouped=np.stack([observer.synthesize(nodes*(tags==j)[None,:,None]) for j in range(len(edges)-1)],axis=1)
    audio=grouped.sum(axis=1);direct=observer.synthesize(nodes)
    assert abs(audio-direct).max()<2e-12
    result=dict(nodes=nodes,grouped_audio=grouped,audio=audio,**analyze(audio,len(observer.orders),root,bands),**measure(grouped,root,bands))
    for prefix,pk,ck in (('line','power','cross'),('broad','broadband_power','broadband_cross')):
        result.update({prefix+'_group_'+k:v for k,v in summary(result[prefix+'_Gram']).items()})
        slices=np.array_split(np.arange(len(result[pk])),3)
        for f in ('mean','CV','complex_coherence'):
            result['chunks_'+prefix+'_'+f]=np.stack([power_statistics(result[pk][s],result[ck][s])[f] for s in slices])
    diff=result['coefficients']-target
    result['coefficient_relative_error']=np.sqrt((abs(diff)**2).sum(axis=0))/np.maximum(np.sqrt((abs(target)**2).sum(axis=0)),1e-24)
    residue=audio-source_audio
    result['wave_NRMSE']=np.array(np.linalg.norm(residue)/max(np.linalg.norm(source_audio),1e-24))
    result['wave_region_NRMSE']=np.array([np.linalg.norm(residue[s])/max(np.linalg.norm(source_audio[s]),1e-24) for s in (slice(0,2048),slice(2048,-2048),slice(-2048,None))])
    result['chunk_rows']=np.array([len(s) for s in slices])
    return result

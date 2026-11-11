"""Measured-peak family tracker with explicit relative-power rejection."""
import numpy as np
from scipy import signal

def peaks(hz,power):
    db=10*np.log10(np.maximum(power,1e-30))
    indices,properties=signal.find_peaks(db,prominence=4)
    keep=(hz[indices]>=35)&(hz[indices]<1200)&(db[indices]>=db.max()-30)
    indices,prominence=indices[keep],properties['prominences'][keep]
    a,b,c=db[indices-1],db[indices],db[indices+1]
    den=a-2*b+c;offset=np.divide(.5*(a-c),den,out=np.zeros_like(a),where=abs(den)>1e-12)
    return hz[indices]+np.clip(offset,-.5,.5)*(hz[1]-hz[0]),prominence

def follow(hz,times,power,start,stop,anchor,reference=5):
    chosen=np.flatnonzero((times>=start-1e-8)&(times<=stop+1e-8))
    multiples=tuple(k for k in (2,3,5,7,10,15,20) if k!=reference)
    nodes=[]
    for i in chosen:
        f,p=peaks(hz,power[:,i]);keep=(f/reference>=15)&(f/reference<=80)
        roots=f[keep]/reference;scores=np.clip(p[keep],0,40)/40;support=[]
        for root in roots:
            found=[]
            for order in multiples:
                if not len(f):found.append(0.);continue
                distance=abs(f-order*root);j=int(np.argmin(distance))
                found.append(float(np.clip(p[j],0,40)/40) if distance[j]<=max(6,.025*order*root) else 0.)
            support.append(found)
        if len(roots):scores+=np.sum(support,axis=1)
        nodes.append(dict(root=roots,score=scores,support=support))
    if len(chosen)<3 or any(not len(n['root']) for n in nodes):return dict(status='missing_reference',rows=[])
    distance=abs(np.log2(nodes[0]['root']/anchor));score=np.where(distance<=.12,nodes[0]['score']-(distance/.12)**2,-np.inf)
    links=[]
    for j in range(1,len(nodes)):
        velocity=np.log2(nodes[j]['root'][:,None]/nodes[j-1]['root'][None,:])/(times[chosen[j]]-times[chosen[j-1]])
        cost=score[None,:]-.025*velocity**2;cost[abs(velocity)>16]=-np.inf
        link=np.argmax(cost,axis=1);score=cost[np.arange(len(link)),link]+nodes[j]['score'];links.append(link)
    if not np.isfinite(score).any():return dict(status='disconnected',rows=[])
    path=[int(np.argmax(score))]
    for link in reversed(links):path.append(int(link[path[-1]]))
    path.reverse()
    rows=[dict(seconds=float(times[i]),root_hz=float(n['root'][k]),support=n['support'][k]) for i,n,k in zip(chosen,nodes,path)]
    return dict(status='measured_connected',reference=reference,rows=rows,
        rule='4dB prominence, within30dB of maximum low-band power, no missing-peak fill,16oct/s continuity; acoustic root only')

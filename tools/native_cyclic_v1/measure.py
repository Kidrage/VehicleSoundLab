"""Native-sample periodic projection and power regression; no waveform resampling."""
import numpy as np
from scipy import linalg,signal


class Coordinate:
    def __init__(self,source_seconds,start,frames,rate,harmonics,minimum_diagonal=.1):
        if len(source_seconds)!=14336 or np.min(np.diff(source_seconds))<=0:
            raise ValueError('Expected immutable monotonic14x1024 phase positions')
        time=start+np.arange(frames)/rate
        # Last observed native full-cycle endpoint is13, not14.
        inside=(time>=source_seconds[0])&(time<source_seconds[13*1024])
        self.indices=np.flatnonzero(inside)
        self.phase=np.interp(time[inside],source_seconds,np.arange(len(source_seconds))/1024)
        self.cycles=np.floor(self.phase).astype(int)
        angle=2*np.pi*self.phase[:,None]*np.arange(1,harmonics+1)[None,:]
        self.basis=np.column_stack([np.ones(len(angle)),np.cos(angle),np.sin(angle)])
        self.q,self.r=linalg.qr(self.basis,mode='economic')
        self.minimum_diagonal=float(np.min(abs(np.diag(self.r))))
        if self.minimum_diagonal<minimum_diagonal:raise ValueError('Periodic design rank unsupported')
        self.full_cycles=13

    def decompose(self,values):
        coefficients=linalg.solve_triangular(self.r,self.q.T@values)
        coherent=self.basis@coefficients
        return coherent,values-coherent,coefficients


def statistic(features,settings):
    def score(value):
        first=value[:,::2].mean(axis=1);second=value[:,1::2].mean(axis=1)
        return (first*second.conj()).real.mean(axis=(1,2))
    observed=score(features);null=[];rng=np.random.default_rng(settings['seed'])
    orders=np.arange(1,settings['harmonics']+1)
    for _ in range(settings['permutations']):
        phase=rng.uniform(0,2*np.pi,features.shape[1])
        changed=features*np.exp(-1j*phase[:,None]*orders[None,:])[None,:,None,:]
        null.append(float(max(score(changed))))
    null=np.array(null)
    p=np.array([(1+sum(null>=v))/(len(null)+1) for v in observed])
    return observed,null,p


def measure(audio,coordinate,bands,settings):
    filtered=[]
    for lo,hi in bands:
        sos=signal.butter(settings['filter_order'],[lo,hi],fs=48000,btype='bandpass',output='sos')
        filtered.append(signal.sosfiltfilt(sos,audio,axis=0)[coordinate.indices])
    full=np.stack(filtered,axis=1) # native frames,bands,LR
    matrix=full.reshape(len(full),-1)
    coherent,residual,coefficients=coordinate.decompose(matrix)
    residual=residual.reshape(full.shape);coherent=coherent.reshape(full.shape)
    output={};saved={'full':full,'coherent':coherent,'residual':residual,'coefficients':coefficients}
    trim=settings['trim_cycles'];cycles=range(trim,coordinate.full_cycles-trim)
    designs={}
    for cycle in cycles:
        at=np.flatnonzero(coordinate.cycles==cycle)
        angle=2*np.pi*coordinate.phase[at,None]*np.arange(1,settings['harmonics']+1)[None,:]
        design=np.column_stack([np.ones(len(at)),np.cos(angle),np.sin(angle)])
        designs[cycle]=(at,design)
    for route,values in [('full',full),('residual',residual)]:
        powers=values**2;dc=[];beta=[]
        for cycle,(at,design) in designs.items():
            fit=linalg.lstsq(design,powers[at].reshape(len(at),-1),lapack_driver='gelsy')[0]
            fit=fit.reshape(1+2*settings['harmonics'],len(bands),2)
            dc.append(fit[0]);beta.append((fit[1:1+settings['harmonics']]-1j*fit[1+settings['harmonics']:]).transpose(1,2,0))
        level=np.mean(dc,axis=0)
        features=np.array(beta).transpose(1,0,2,3)/np.maximum(level,settings['minimum_energy_FS2'])[:,None,:,None]
        features[np.max(level,axis=1)<settings['minimum_energy_FS2']]=0
        observed,null,p=statistic(features,settings)
        rows=[dict(band_hz=band,power_LR=level[i].tolist(),train_heldout_cross_statistic=float(observed[i]),
            familywise_p=float(p[i]),periodic_residual_power_supported=bool(observed[i]>0 and p[i]<=settings['familywise_p']))
            for i,band in enumerate(bands)]
        output[route]=dict(bands=rows,max_null=null.tolist(),interior_cycles=len(designs),
            train_cycles=(len(designs)+1)//2,heldout_cycles=len(designs)//2)
        saved[route+'_features']=features;saved[route+'_cycle_DC']=np.array(dc)
    output['decomposition']=dict(
        coherent_power=np.mean(coherent**2,axis=0).tolist(),residual_power=np.mean(residual**2,axis=0).tolist(),
        cross_power=np.mean(coherent*residual,axis=0).tolist(),
        periodic_basis_max_normal_residual=float(np.max(abs(coordinate.basis.T@residual.reshape(len(full),-1)))/len(full)),
        complete_cycles=coordinate.full_cycles,native_frames=len(full),minimum_QR_diagonal=coordinate.minimum_diagonal,
        finite_noise_bias_and_common_fit=True,physical_source_separation=False)
    return output,saved

"""Moving local supports within nonoverlapping harmonic cells, no resynthesis."""
import numpy as np


def measure(audio, plan, cycles):
    n = cycles*plan['cycle_frames']; support=max(plan['cycles'])*plan['cycle_frames']//2
    centers=np.arange(support,len(audio)-support+1,plan['hop'])
    starts=centers-n//2
    window=.5-.5*np.cos(2*np.pi*np.arange(n)/n)
    frame=audio[starts[:,None]+np.arange(n)]*window[None,:,None]
    z=np.fft.rfft(frame,axis=1)
    power=abs(z)**2*2/(n*np.sum(window**2))
    power[:,0]*=.5;power[:,-1]*=.5
    timed=np.sum(frame**2,axis=1)/np.sum(window**2)
    parseval=float(np.max(abs(power.sum(axis=1)-timed)/np.maximum(timed,1e-30)))
    hz=np.fft.rfftfreq(n,1/plan['sample_rate'])
    root=plan['sample_rate']/plan['cycle_frames']
    h=np.arange(1,int(np.floor(max(b[1] for b in plan['bands'])/root))+1)
    h=h[h*root>=min(b[0] for b in plan['bands'])]
    cell=np.empty((len(centers),len(h),2));moving={};fixed={};offsets={}
    for width in plan['support_bins']:
        moving[width]=np.empty_like(cell);fixed[width]=np.empty_like(cell);offsets[width]=np.empty_like(cell)
    for i,k in enumerate(h):
        bins=np.flatnonzero((hz>=(k-.5)*root)&(hz<(k+.5)*root))
        assert len(bins)==cycles
        p=power[:,bins]
        cell[:,i]=p.sum(axis=1)
        for width in plan['support_bins']:
            candidates=np.array([p[:,at:at+width].sum(axis=1) for at in range(len(bins)-width+1)])
            best=np.argmax(candidates,axis=0)
            moving[width][:,i]=np.max(candidates,axis=0)
            offsets[width][:,i]=(bins[best]+width//2-k*cycles)/cycles
            center_bin=k*cycles
            nominal=np.flatnonzero(abs(bins-center_bin)<=width//2)
            assert len(nominal)==width
            fixed[width][:,i]=p[:,nominal].sum(axis=1)
    masks=np.array([(h*root>=a)&(h*root<b) for a,b in plan['bands']])
    band_power=np.einsum('thc,bh->tbc',cell,masks)
    arrays=dict(centers=centers,harmonic=h,cell_power=cell,band_power=band_power)
    rows=[]
    for width in plan['support_bins']:
        moving_band=np.einsum('thc,bh->tbc',moving[width],masks)
        fixed_band=np.einsum('thc,bh->tbc',fixed[width],masks)
        concentration=moving_band.sum(axis=0)/band_power.sum(axis=0)
        nominal=fixed_band.sum(axis=0)/band_power.sum(axis=0)
        assert np.min(concentration)>=0 and np.max(concentration)<=1+1e-12
        assert np.min(concentration-nominal)>-1e-12
        rows.append(dict(width=width,concentration_LR=concentration.tolist(),
            nominal_concentration_LR=nominal.tolist(),mean_band_power_LR=band_power.mean(axis=0).tolist()))
        arrays.update({f'moving_{width}':moving[width],f'fixed_{width}':fixed[width],f'offset_cells_{width}':offsets[width]})
    errors=[]
    for f in sorted({0,len(starts)//2,len(starts)-1}):
        for bin_index in (36*cycles-1,103*cycles,150*cycles+2):
            # Integer modular reduction avoids large-angle cancellation at
            # exact Hann nulls; this remains a direct trigonometric sum.
            phase=2*np.pi*((bin_index*np.arange(n))%n)/n
            direct=(np.cos(phase)-1j*np.sin(phase))@frame[f]
            floor=max(float(abs(z[f]).max())*1e-6,1e-20)
            errors.append(float(np.max(abs(direct-z[f,bin_index])/np.maximum(abs(z[f,bin_index]),floor))))
    return dict(cycles=cycles,window_frames=n,window_seconds=n/plan['sample_rate'],
        native_grid_hz=plan['sample_rate']/n,frames=len(centers),
        center_seconds=[float(centers[0]/48000),float(centers[-1]/48000)],rows=rows,
        parseval_relative_error=parseval,direct_DFT_relative_error=max(errors)),arrays

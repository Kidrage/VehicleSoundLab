"""Signed multiband fourth moments and a finite energy covariance partition."""
import numpy as np


def connected(values,weights=None):
    x=np.asarray(values);w=np.full(len(x),1/len(x)) if weights is None else np.asarray(weights)
    if abs(w.sum()-1)>1e-12 or np.any(w<0):raise ValueError('Probability weights required')
    mean=w@x;y=x-mean;second=y.T@(y*w[:,None]);squares=y*y
    fourth=squares.T@(squares*w[:,None]);v=np.diag(second)
    if np.any(v<=0):raise ValueError('Resolved positive variances required')
    squared_covariance=fourth-np.outer(v,v);cumulant=squared_covariance-2*second*second
    return dict(mean=mean,second=second,fourth=fourth,squared_covariance=squared_covariance,
        connected=cumulant,normalized_connected=cumulant/np.outer(v,v))


def energy_partition(power,tile):
    power=np.asarray(power);tile=np.asarray(tile);mean=power.mean(axis=0);centered=power-mean
    if np.any(mean<=0):raise ValueError('Resolved positive power required')
    total=centered.T@centered/len(power);within=np.zeros_like(total);between=np.zeros_like(total);residual=np.empty_like(power);groups=[]
    for index in np.unique(tile):
        select=tile==index;values=power[select];local=values.mean(axis=0);r=values-local;weight=len(values)/len(power)
        covariance=r.T@r/len(values);within+=weight*covariance;between+=weight*np.outer(local-mean,local-mean);residual[select]=r
        groups.append(dict(tile=int(index),windows=len(values),mean=local,covariance=covariance))
    error=float(abs(total-within-between).max());assert error<1e-20+1e-12*float(abs(total).max())
    lagged=[];counts=[]
    for lag in range(-5,6):
        left=np.arange(max(0,-lag),min(len(power),len(power)-lag));right=left+lag
        same=tile[left]==tile[right];left=left[same];right=right[same]
        if not len(left):raise ValueError('No within-tile lag support')
        lagged.append(residual[left].T@residual[right]/len(left));counts.append(len(left))
    scale=np.outer(mean,mean)
    return dict(mean=mean,total=total,within=within,between=between,normalized_total=total/scale,
        normalized_within=within/scale,normalized_between=between/scale,groups=groups,residual=residual,
        lags_ms=np.arange(-5,6)*10,lagged=np.array(lagged),normalized_lagged=np.array(lagged)/scale,lag_counts=np.array(counts),identity_error=error)


def known():
    from numpy.polynomial.hermite import hermgauss
    node,w=hermgauss(9);z=np.stack(np.meshgrid(node*np.sqrt(2),node*np.sqrt(2),indexing='ij'),axis=-1).reshape(-1,2);w=np.outer(w,w).ravel()/np.pi
    correlated=z@np.array([[1,.6],[0,.8]])
    gaussian=connected(correlated,w);assert abs(gaussian['connected']).max()<1e-12
    assert abs(gaussian['squared_covariance'][0,1]-.72)<1e-12
    p=.2;shared=connected(np.vstack((z/np.sqrt(p),np.zeros_like(z))),np.r_[w*p,w*(1-p)])
    independent_x=[];independent_w=[]
    for b0 in [0,1]:
        for b1 in [0,1]:
            independent_x.append(z*np.array([b0,b1])/np.sqrt(p));independent_w.append(w*(p if b0 else 1-p)*(p if b1 else 1-p))
    independent=connected(np.concatenate(independent_x),np.concatenate(independent_w))
    assert abs(shared['normalized_connected'][0,1]-4)<1e-12 and abs(independent['normalized_connected'][0,1])<1e-12
    assert abs(np.diag(shared['normalized_connected'])-12).max()<1e-12
    assert abs(np.diag(shared['normalized_connected'])-np.diag(independent['normalized_connected'])).max()<1e-12
    rng=np.random.default_rng(418279);tile=np.repeat([0,1,2],[7,13,19]);base=rng.uniform(.2,1,(len(tile),4))
    base[:,1]=2-base[:,0];base[:,2]+=tile*.4;result=energy_partition(base,tile)
    assert result['total'][0,1]<0 and result['within'][0,1]<0
    scaled=energy_partition(base*.013,tile);permutation=[2,0,3,1];swapped=energy_partition(base[:,permutation],tile)
    for key in ['normalized_total','normalized_within','normalized_between','normalized_lagged']:
        assert abs(scaled[key]-result[key]).max()<1e-12
        assert abs(swapped[key]-result[key][...,permutation,:][...,:,permutation]).max()<1e-12
    return dict(correlated_Gaussian_connected_max=float(abs(gaussian['connected']).max()),
        correlated_Gaussian_squared_covariance=float(gaussian['squared_covariance'][0,1]),
        shared_scale_cross=float(shared['normalized_connected'][0,1]),independent_scale_cross=float(independent['normalized_connected'][0,1]),
        both_scale_marginal_excess=np.diag(shared['normalized_connected']).tolist(),unequal_group_identity_error=result['identity_error'],
        signed_negative_cross=True,gain_and_channel_permutation=True),dict(gaussian_input=correlated,gaussian_weights=w,
        shared_input=np.vstack((z/np.sqrt(p),np.zeros_like(z))),shared_weights=np.r_[w*p,w*(1-p)],
        independent_input=np.concatenate(independent_x),independent_weights=np.concatenate(independent_w),power=base,tile=tile)

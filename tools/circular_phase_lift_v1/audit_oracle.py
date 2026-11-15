"""Independent interpolation, binary CDF and SciPy observer audit formulas."""
import math
import numpy as np
from scipy import signal, special


def inverse(table, normal):
    count = len(table)
    nodes = np.r_[0., (np.arange(count)+.5)/count, 1.]
    probability = special.ndtr(normal)
    return np.column_stack([np.interp(probability[:, j], nodes,
        np.r_[table[0, j], table[:, j], table[-1, j]]) for j in range(table.shape[1])])


def phase(product, uniform, knots, cdf, lower, upper):
    index = np.clip(np.searchsorted(knots, product, side='right')-1, 0, len(knots)-2)
    weight = np.clip((product-knots[index])/(knots[index+1]-knots[index]), 0., 1.)
    def edge(j):
        return (1-weight)*cdf[index, j]+weight*cdf[index+1, j]
    lo = np.zeros(len(product), dtype=int)
    hi = np.full(len(product), len(lower)-1, dtype=int)
    while np.any(lo < hi):
        mid = (lo+hi)//2
        left = uniform < edge(mid+1)
        hi = np.where(left, mid, hi)
        lo = np.where(left, lo, mid+1)
    a, b = edge(lo), edge(lo+1)
    return lower[lo]+(uniform-a)/(b-a)*(upper[lo]-lower[lo])


def fields(model, capture, frames):
    h, k = len(model['fixed_phase']), len(model['rho'])
    rho = np.r_[model['rho'], model['residual_rho']]
    amplitude = np.empty((frames, h, 2))
    common = np.empty((frames, h))
    uniform = np.empty((frames, h))
    for first in range(0, frames, 1024):
        n = np.arange(first, min(first+1024, frames))
        u = (n%256/256.)[:, None]
        normal = []
        for name in ('state', 'independent_state'):
            state = capture[name]
            q = ((1-u)*state[n//256]+u*state[n//256+1])/np.sqrt((1-u)**2+u*u+2*rho*u*(1-u))
            normal.append(np.einsum('nk,dk->nd', q[:, :k], model['basis'], optimize=False)+q[:, k:]*model['residual_std'])
        amplitude[n] = inverse(model['amplitude'], normal[0][:, :2*h]).reshape(-1, h, 2)
        common[n] = inverse(model['phase'][:, :h], normal[0][:, 2*h:3*h])
        uniform[n] = special.ndtr(normal[1][:, 3*h:])
    return amplitude, common, uniform


def statistics(power, cross):
    mean = power.mean(axis=0)
    centered = power-mean
    covariance = np.cov(power, rowvar=False, bias=True)
    valid = mean > 1e-24
    cv = np.divide(np.sqrt(np.maximum(0., np.diag(covariance))), mean, out=np.zeros_like(mean), where=valid)
    denominator = np.sqrt(mean[::2]*mean[1::2])
    stereo_valid = denominator > 1e-24
    cross_mean = cross.mean(axis=0)
    return dict(mean=mean, covariance=covariance, CV=cv, power_defined=valid,
        complex_coherence=np.divide(cross_mean, denominator, out=np.zeros(len(denominator), complex), where=stereo_valid),
        coherence_defined=stereo_valid, mid_power=(mean[::2]+mean[1::2]+2*cross_mean.real)/4,
        side_power=(mean[::2]+mean[1::2]-2*cross_mean.real)/4,
        lag_covariance=np.array([np.einsum('ni,nj->ij', centered[:-j], centered[j:], optimize=False)/(len(power)-j)
                                for j in range(1,min(9,len(power))) ]))


def observe(grouped, root, bands):
    flat = grouped.reshape(len(grouped), -1)
    frequency, _, transform = signal.stft(flat.T, fs=1024*root, window='hann', nperseg=4096,
        noverlap=3840, boundary=None, padded=False)
    starts = np.arange(0, len(flat)-4096+1, 256)
    orders = np.arange(1, 289)
    total = transform.reshape(6, 2, len(frequency), len(starts)).sum(axis=0)
    z = np.moveaxis(total[:, 4*orders], (0,1,2), (2,1,0))*2
    z *= np.exp(-2j*np.pi*np.remainder(starts[:, None]*orders/1024, 1))[..., None]
    weights = np.full(len(frequency), 4/3)
    weights[[0,-1]] = 2/3
    gram, line, line_cross, broad, broad_cross = {}, [], [], [], []
    for prefix in ('line','broad'):
        matrices = []
        for low, high in bands:
            index = 4*orders[(orders*root >= low)&(orders*root < high)] if prefix == 'line' else np.flatnonzero((frequency >= low)&(frequency < high))
            scale = np.full(len(index),2.) if prefix == 'line' else weights[index]
            matrices.append(np.einsum('ikt,jkt,k->tij',transform[:,index],transform[:,index].conj(),scale,optimize=False))
        gram[prefix] = np.stack(matrices,axis=1)
    for low, high in bands:
        mask = (orders*root >= low)&(orders*root < high)
        line.append((abs(z[:,mask])**2).sum(axis=1)/2)
        line_cross.append((z[:,mask,0]*z[:,mask,1].conj()).sum(axis=1)/2)
        mask = (frequency >= low)&(frequency < high)
        broad.append((abs(total[:,mask])**2*weights[mask,None]).sum(axis=1).T)
        broad_cross.append((total[0,mask]*total[1,mask].conj()*weights[mask,None]).sum(axis=0))
    all_frequency = np.einsum('ikt,jkt,k->tij',transform,transform.conj(),weights,optimize=False)
    window = signal.windows.hann(4096,sym=False)
    time_energy = np.array([(flat[start:start+4096]*window[:,None]).T@(flat[start:start+4096]*window[:,None])/np.dot(window,window) for start in starts])
    return dict(coefficients=z, power=np.concatenate(line,axis=1), cross=np.stack(line_cross,axis=1),
        broadband_power=np.concatenate(broad,axis=1),broadband_cross=np.stack(broad_cross,axis=1),
        line_Gram=gram['line'],broad_Gram=gram['broad'],all_frequency_Gram=all_frequency,time_energy_Gram=time_energy)


def group_summary(matrix):
    m = matrix.mean(axis=0)
    self_power = np.diagonal(m,axis1=-2,axis2=-1).real.reshape(4,6,2)
    power = np.array([[math.fsum(m[b,2*g+c,2*h+c].real for g in range(6) for h in range(6)) for c in (0,1)] for b in range(4)])
    rest = np.array([[math.fsum(m[b,2*g+c,2*h+c].real for g in range(1,6) for h in range(1,6)) for c in (0,1)] for b in range(4)])
    cross = np.array([[2*math.fsum(m[b,c,2*h+c].real for h in range(1,6)) for c in (0,1)] for b in range(4)])
    lr = np.array([sum(m[b,2*g,2*h+1] for g in range(6) for h in range(6)) for b in range(4)])
    return dict(group_self_power=self_power, low_power=self_power[:,0],rest_power=rest,
        signed_low_rest_cross=cross,signed_all_group_cross=power-self_power.sum(axis=1),total_power=power,complex_LR=lr)

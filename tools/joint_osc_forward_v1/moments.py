"""Exact Gaussian complex moments, including finite-window signed cross power."""
import numpy as np


def coefficients(spec,covariance,amplitude_map):
    L=np.zeros_like(spec['phase_map']);L[spec['selected']]=amplitude_map
    P=spec['phase_map'];q=L+1j*P;v=np.einsum('mi,ij,mj->m',L,covariance,L)
    normalization=np.exp(-v)
    first=normalization*np.exp(.5*np.einsum('mi,ij,mj->m',q,covariance,q))
    plus=q[:,None,:]+q[None,:,:];minus=q[:,None,:]+q.conj()[None,:,:]
    factor=normalization[:,None]*normalization[None,:]
    same=factor*np.exp(.5*np.einsum('mni,ij,mnj->mn',plus,covariance,plus))
    opposite=factor*np.exp(.5*np.einsum('mni,ij,mnj->mn',minus,covariance,minus))
    return first,same,opposite


def finite_power(spec,covariance,amplitude_map,deterministic,audio):
    first,same,opposite=coefficients(spec,covariance,amplitude_map)
    trim=12000;w=.5-.5*np.cos(2*np.pi*np.arange(len(audio)-2*trim)/(len(audio)-2*trim));w/=w.sum()
    phase=np.exp(1j*deterministic[trim:-trim]);amplitude=spec['amplitude']
    plus=phase.T@(phase*w[:,None]);minus=phase.T@(phase.conj()*w[:,None])
    matrix=.5*(same*plus+opposite*minus).real*amplitude[:,None]*amplitude[None,:]
    expected=float(matrix.sum());diagonal=float(np.trace(matrix));cross=expected-diagonal
    realized=float(np.dot(w,audio[trim:-trim]**2))
    return dict(expected_modal_second_moment=matrix,expected_total=expected,expected_diagonal=diagonal,
        expected_signed_cross=cross,realized=realized,realized_over_expected=realized/expected,
        theoretical_first=first,theoretical_same=same,theoretical_opposite=opposite)


def at_times(spec,covariance,amplitude_map,theta):
    first,same,opposite=coefficients(spec,covariance,amplitude_map)
    e=np.exp(1j*theta);a=spec['amplitude']
    mean=(e@(a*first)).real
    second=.5*np.einsum('tm,mn,tn->t',e*a,same,e*a).real
    second+=.5*np.einsum('tm,mn,tn->t',e*a,opposite,(e*a).conj()).real
    return mean,second

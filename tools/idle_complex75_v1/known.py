"""Known acoustic coordinates, finite filter images and joint Gaussian gain controls."""
import numpy as np
from scipy import signal
from numpy.polynomial.hermite import hermgauss
from idle_window_transfer_v1.observe import design
from idle_complex75_v1.extract import extract,INDICES,response
from idle_complex75_v1.model import covariance,table,gain


def run():
    freq=np.array([36,76,112,152,188,224,264,284,300,360,376,472,488]);t=np.arange(144000)/48000
    theta=2*np.pi*t[:,None]*freq;z=np.exp(1j*theta[:,[1,2,4]]);A=design(freq,z)
    beta=np.random.default_rng(914713).normal(0,.01,27);beta[1]=.08;beta[14]=-.02;reference=beta[1]-1j*beta[14]
    control=extract(A@beta,freq,z);zero=float(abs(control['latent']).max());assert zero<1e-10
    # NonlinearFM fully supplied to the coordinate basis, no amplitude variation.
    zfm=z*np.exp(.23j*np.sin(2*np.pi*t[:,None]*[1.1,2.3,3.7]));fm=extract(design(freq,zfm)@beta,freq,zfm)
    fm_error=float(abs(fm['latent']).max());assert fm_error<1e-10
    terms=[(4.,.15/2),(-4.,.15/2),(7.2,.11/2),(-7.2,-.11/2)]
    perturbation=sum(value*np.exp(2j*np.pi*f*t) for f,value in terms)
    audio=A@beta+(reference*z[:,0]*perturbation).real;measured=extract(audio,freq,z)
    expected=np.zeros(len(INDICES),complex);time=t[INDICES]
    for f,value in terms:
        expected+=value*response(measured['taps'],[f])[0]*np.exp(2j*np.pi*f*time)
        image=-2*freq[1]-f
        expected+=reference.conjugate()/reference*value.conjugate()*response(measured['taps'],[image])[0]*np.exp(2j*np.pi*image*time)
    error=float(abs(measured['relative_envelope']-1-expected).max());assert error<1e-10
    neighbor=extract(A@beta+.01*np.cos(2*np.pi*(freq[1]+7.2)*t),freq,z)
    neighbor_std=float(np.std(neighbor['latent'][:,0]));assert neighbor_std>.01
    cases=[];quadrature_nodes,quadrature_weights=hermgauss(9);quadrature_nodes*=np.sqrt(2);quadrature_weights/=np.sqrt(np.pi)
    zz=np.stack(np.meshgrid(quadrature_nodes,quadrature_nodes,indexing='ij'),axis=-1).reshape(-1,2);W=np.outer(quadrature_weights,quadrature_weights).ravel()
    for name in ['delayed','AM','phase','zero']:
        h=np.zeros((8,2,2))
        if name=='delayed':h[0,0,0]=.12;h[2,1,0]=.07;h[0,1,1]=.08
        elif name=='AM':h[0,0,0]=.12
        elif name=='phase':h[0,1,0]=.12
        model=dict(taps=h);compiled=table(model);C=covariance(h)[0]
        e,U=np.linalg.eigh(C);samples=zz@(U*np.sqrt(np.maximum(e,0))).T;g=gain(samples,C)
        eg=float(np.exp(-.5*np.trace(C)));power_error=float(abs(W@(abs(g)**2)-1));mean_error=float(abs(W@g-eg))
        assert power_error<1e-10 and mean_error<1e-10
        cases.append(dict(name=name,marginal_error=compiled['error'],E_power_error=power_error,E_mean_error=mean_error))
    return dict(constant_error=zero,nonlinear_FM_false_latent=fm_error,exact_filtered_complex_error=error,
        neighbor_survives_std=neighbor_std,Gaussian_gain_controls=cases,source_separation_claimed=False),dict(
        frequencies=freq,base_audio=A@beta,phasors=z,FM_phasors=zfm,beta=beta,complex_audio=audio,
        expected_relative_envelope=1+expected,measured_relative_envelope=measured['relative_envelope'],
        measured_latent=measured['latent'])

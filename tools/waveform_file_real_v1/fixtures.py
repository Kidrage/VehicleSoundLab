"""Small analytic CONTROLS, never real-source voice generators."""
import numpy as np
from observer_frequency_v1.reduced_oracle import synthesize


def cases():
    orders = np.array([5,65,110,140,185,300])
    scales = np.array([.19,.13,.09,.08,.06,.04])[:,None]
    for label,N in (('independent_unequal',4609),('phase_delay_right',4353),('silent_right',4865),('both_zero',4609)):
        positions = np.array([0,int(.167*(N-1)),int(.433*(N-1)),int(.709*(N-1)),N-1])
        outer = np.r_[np.arange(-2048,0,256),positions,positions[-1]+np.arange(256,2049,256)]+2048
        q = np.empty((len(outer),len(orders),2),complex)
        t = outer[:,None]/1024
        h = np.arange(len(orders))[None,:]
        q[:,:,0] = (1+.12*np.sin(.37*t+.43*h))*np.exp(1j*(.29*h+.08*np.cos(.51*t+.2*h)))
        q[:,:,1] = (.31+.08*np.cos(.63*t+.73*h))*np.exp(1j*(1.1+.81*h+.19*np.sin(.41*t+.3*h)))
        if label=='phase_delay_right':
            delay=.00035*65536
            q[:,:,1] = .63*q[:,:,0]*np.exp(-2j*np.pi*orders[None,:]*delay/1024)
        if label=='silent_right': q[:,:,1]=0
        if label=='both_zero': q[:]=0
        audio=synthesize(q*scales[None],outer,orders,N+4096)
        if label!='both_zero':
            # Off-model DC/Nyquist residuals exercise BOTH real-FFT end caps.
            n=np.arange(len(audio)); endpoint=1e-6*(1+(-1.)**n)
            audio[:,0]+=endpoint
            if label!='silent_right': audio[:,1]+=.37*endpoint
        yield dict(label=label,audio=audio,target=audio[2048:-2048].copy(),
            original_positions=positions,positions=outer,orders=orders,scale=scales,source_nodes=q)

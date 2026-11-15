"""Independent full root-Frobenius trace using every Hann frequency bin.

For each real/imaginary OSC pair, squared real data-column norms sum to the
weighted norm of its complex carrier. Integer carrier shifts are EXACT bin
shifts in the4096-point window. Only the node-root envelope FFTs are needed.
This is an audit identity, never a production normal-equation solve.
"""
import numpy as np
from scipy import linalg
from observer_complete_v1.audit_oracle import hats


def root_frobenius(oracle):
    N,C=oracle.audio.shape;M,H,_=oracle.shape;profile=oracle.profile
    orders=np.asarray(oracle.orders)
    if np.any(orders!=orders.astype(int)) or np.any((orders<1)|(orders>511)):
        raise ValueError('Only the original integer1024-cycle carrier basis is covered')
    L=np.linalg.cholesky(oracle.R)
    inverse=linalg.solve_triangular(L.T,np.eye(M),lower=False)
    envelopes=hats(oracle.positions,N).T@inverse
    power_scales=oracle.scale[:,0]**2
    waveform=float(power_scales.sum()*np.sum(envelopes**2)/profile['sigma']**2)
    weights=np.r_[profile['weights'],profile['weights'][-2:0:-1]]**2
    effective=np.zeros(4096)
    for order,scale in zip(orders,power_scales):effective+=scale*np.roll(weights,-4*int(order))
    frequency_energy=np.zeros(4096)
    window=.5-.5*np.cos(2*np.pi*np.arange(4096)/4096)
    for start in range(0,N-4096+1,256):
        gain=profile['amplitude']*window/np.sqrt(profile['full_coverage'][start:start+4096])
        transformed=np.fft.fft(envelopes[start:start+4096]*gain[:,None],axis=0)
        frequency_energy+=np.sum(transformed.real**2+transformed.imag**2,axis=1)/4096
    spectral=float(frequency_energy@effective)
    ridge_identity=2*M*H
    return dict(single_channel_data_trace=waveform+spectral,
        single_channel_waveform_trace=waveform,single_channel_spectral_trace=spectral,
        single_channel_identity_trace=ridge_identity,channels=C,
        root_Frobenius=float(np.sqrt(C*(waveform+spectral+ridge_identity))),
        every_frequency_bin=4096,every_order=H,every_node=M,no_order_or_window_truncation=True)

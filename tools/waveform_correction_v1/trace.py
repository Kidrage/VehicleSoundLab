"""Original all-bin finite-metric Frobenius without root approximations."""
import numpy as np
from scipy import linalg


def original_frobenius(positions,orders,scale,metric,node_L,channels):
    N=metric.frame.frames;M=len(positions);H=len(orders)
    if channels not in (1,2) or node_L.shape!=(M,M):raise ValueError('Declared mono/stereo node root required')
    if np.any(orders!=np.asarray(orders,int)) or np.any((orders<1)|(orders>511)):
        raise ValueError('Original1024-cycle integer carriers required')
    basis=np.array([np.interp(np.arange(N),positions,row) for row in np.eye(M)])
    envelopes=linalg.solve_triangular(node_L,basis,lower=True)
    powers=np.asarray(scale[:,0])**2
    waveform=float(np.sum(envelopes**2)*sum(powers)/metric.wave_scale**2)
    weights=np.r_[metric.weights,metric.weights[-2:0:-1]]**2
    spectral=0.
    for start in metric.frame.starts[metric.keep]:
        gain=metric.amplitude_scale*metric.frame.window/np.sqrt(metric.frame.coverage[start:start+4096])
        transformed=np.fft.fft(envelopes[:,start:start+4096]*gain[None],axis=1)
        energy=np.sum(transformed.real**2+transformed.imag**2,axis=0)/4096
        for order,power in zip(orders,powers):
            spectral+=float(power*(np.roll(energy,4*int(order))@weights))
    return dict(root_Frobenius=float(np.sqrt(channels*(waveform+spectral+2*M*H))),
        waveform_trace_single_channel=waveform,spectral_trace_single_channel=spectral,
        all_bins=4096,all_orders=H,all_nodes=M,channels=channels,
        native_root_norm_NOT_used=True)

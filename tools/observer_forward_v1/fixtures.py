"""Seven declared controls, no material or engine fitting."""
import numpy as np


def inputs():
    n=4608;positions=np.r_[np.arange(0,n-1,256),n-1];t=positions/(n-1);h=3
    constant=np.broadcast_to(np.array([[.7+.2j,.3-.1j],[.2-.1j,.1+.05j],[.04+.03j,-.02+.01j]]),(len(t),h,2)).copy()
    yield 'constant',dict(frames=n,positions=positions,orders=np.array([1,2,3]),observed_orders=np.arange(1,7),nodes=constant)
    yield 'amplitude_ramp',dict(frames=n,positions=positions,orders=np.array([1,2,3]),observed_orders=np.arange(1,7),nodes=constant*(.3+t[:,None,None]))
    yield 'complex_rotation',dict(frames=n,positions=positions,orders=np.array([1,2,3]),observed_orders=np.arange(1,7),nodes=constant*np.exp(5j*t[:,None,None]))
    varied=constant*np.exp(20j*t[:,None,None])*np.cos(30*t[:,None,None])
    yield 'neighbor_and_image_leakage',dict(frames=n,positions=positions,orders=np.array([1,2,3]),observed_orders=np.arange(1,7),nodes=varied)
    silent=varied.copy();silent[:,:,1]=0
    yield 'asymmetric_silent_right',dict(frames=n,positions=positions,orders=np.array([1,2,3]),observed_orders=np.arange(1,7),nodes=silent)
    rng=np.random.default_rng(27183);nodes=rng.normal(size=constant.shape)+1j*rng.normal(size=constant.shape)
    yield 'adjoint',dict(frames=n,positions=positions,orders=np.array([1,2,3]),observed_orders=np.arange(1,7),nodes=nodes)
    yield 'underdetermined_null',dict(frames=n,positions=positions,orders=np.array([2,3]),observed_orders=np.array([2,3]),nodes=np.zeros((len(t),2,1),complex))

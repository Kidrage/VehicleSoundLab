"""Deterministic known coefficients only, including intended complete dimensions."""
import numpy as np


def definitions():
    small=8193
    for name,orders,positions in (
        ('small_stereo_AM_PM',[7,280],[0,2341,small-1]),
        ('small_silent_right',[7],[0,2341,small-1]),
        ('small_zero',[7,280],[0,2341,small-1]),
        ('small_rank_deficient',[7,280],[0,1,4096,small-1])):
        yield name,small,np.array(positions),np.array(orders)
    frames=18430;original=np.r_[np.arange(0,frames-4096,256),frames-4097]
    positions=np.r_[np.arange(-2048,0,256),original,original[-1]+np.arange(256,2049,256)]+2048
    assert len(positions)==73 and positions[-1]==frames-1
    yield 'full288_73_AM_PM_sweep_weak',frames,positions,np.arange(1,289)


def nodes(name,positions,orders):
    t=positions[:,None]/positions[-1];h=orders[None,:]
    phase=.3*h+.03*h*np.sin(2*np.pi*.7*t)+.0002*h*t*t
    amplitude=1+.08*np.sin(2*np.pi*3*t+.3*h)
    q=np.empty((len(positions),len(orders),2),complex)
    q[:,:,0]=amplitude*np.exp(1j*phase)
    q[:,:,1]=.73*(1+.05*np.cos(2*np.pi*2*t+.11*h))*np.exp(1j*(phase+.19*h+.2*np.sin(2*np.pi*t)))
    if name=='small_silent_right':q[:,:,1]=0
    if name=='small_zero':q[:]=0
    return q

"""Fixed analytic source-time signals; never supplied to the phase estimator."""
import numpy as np

ORDERS = np.array([3,5,7,11,15])


def specs():
    common = dict(root=62., slope=0., pm=0., am=0., delay=0., relative_pm=0.,
                  right_ratio=.71, right_phase=.37, reference_gain=1., gap=False)
    changes = [('constant',{}),('linear_sweep',dict(root=58.,slope=2.)),
        ('common_PM',dict(pm=.04)),('independent_AM',dict(am=.22)),
        ('stereo_phase',dict(right_phase=-.83,right_ratio=.43)),
        ('stereo_delay',dict(slope=1.,delay=.00035)),
        ('low_root',dict(root=10.)),
        ('combined',dict(root=58.,slope=2.,pm=.04,am=.22,delay=.00035,relative_pm=.012))]
    return [(name,dict(common,**change)) for name,change in changes]


def cycles(t, spec):
    return spec['root']*t+.5*spec['slope']*t*t+spec['pm']*np.sin(2*np.pi*.55*t)


def formula(t, spec):
    out = np.zeros((len(t),2))
    for channel in (0,1):
        at = t-channel*spec['delay']
        for j,order in enumerate(ORDERS):
            gain = [.07,.2,.065,.04,.025][j]*(spec['right_ratio'] if channel else 1)
            gain = gain*(1+spec['am']*np.sin(2*np.pi*(.7+.13*j)*at+.4*j+.7*channel))
            if order==5:
                gain = gain*spec['reference_gain']
                if spec['gap']:gain = gain*((at<1.88)|(at>2.12))
            phase = 2*np.pi*order*cycles(at,spec)+.13*order+channel*spec['right_phase']
            phase += spec['relative_pm']*(j-2)*np.sin(2*np.pi*1.3*at+.2*channel)
            out[:,channel] += gain*np.cos(phase)
    return out

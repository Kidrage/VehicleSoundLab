"""Known slow root trajectory, scalar motion and independent spectral change."""
import numpy as np


def source(times, root_times, root_values, changed=False):
    rate = 48000
    roots = np.interp(times, root_times, root_values)
    cycles = np.r_[0, np.cumsum((roots[1:]+roots[:-1])/(2*rate))]
    gain = .7+.15*np.sin(2*np.pi*.8*times)
    result = np.zeros((len(times), 2))
    for h in range(1, 289):
        amplitude = .065*np.exp(-h/90)/np.sqrt(h)
        if changed:
            amplitude *= .5 if h >= 46 else np.sqrt(.5) if h >= 19 else 1
        phase = 2*np.pi*h*cycles+h*.17
        side = .02*h+.1*np.sin(h)
        result += gain[:, None]*amplitude*np.column_stack((np.cos(phase), .8*np.cos(phase+side)))
    return result, roots

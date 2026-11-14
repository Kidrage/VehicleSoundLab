"""Short native spectra separate local shape from already modeled broad-band power."""
import numpy as np
from scipy import signal
from idle_phase_difference_v1.features import matrix
from idle_positive_power_v1.model import predict

BANDS = [[1200,2200],[2200,4000],[4000,8000],[8000,14000]]
CENTERS = np.arange(12000,132000,96)
FREQUENCIES = np.fft.rfftfreq(256, 1/48000)


def observe(audio, phasors, law):
    feature = matrix(phasors,hop=1,trim=0)
    q = predict(law,feature)
    w = signal.windows.hann(256,sym=False)
    indices = CENTERS[:,None]+np.arange(-128,128)
    probabilities, filters, inventories = [], [], []
    for band,(lo,hi) in enumerate(BANDS):
        sos = signal.butter(4,[lo,hi],btype='bandpass',fs=48000,output='sos')
        y = signal.sosfilt(sos,audio[:,0])/np.sqrt(q[:,band])
        power = abs(np.fft.rfft(y[indices]*w,axis=1))**2
        bins = np.flatnonzero((FREQUENCIES>=lo)&(FREQUENCIES<hi))
        shape = power[:,bins]
        total = shape.sum(axis=1)
        if np.any(total<=0):raise ValueError('Missing local spectral energy')
        probabilities.append(shape/total[:,None]);filters.append(sos);inventories.append(bins)
    return feature[CENTERS],probabilities,np.array(filters),inventories

"""Demodulated coefficient observations; no engine phase or source-separation claim."""
import numpy as np
from scipy import signal
from idle_phase_difference_v1.features import matrix
from idle_positive_power_v1.model import predict

BANDS=[[1200,2200],[2200,4000],[4000,8000],[8000,14000]]


def observe(audio,z,law,harmonics,groups,kernel):
    phi=z[:,1]*z[:,0].conj();q=predict(law,matrix(z,hop=1,trim=0))
    streams=[]
    for band in BANDS:
        y=signal.sosfilt(signal.butter(4,band,btype='bandpass',fs=48000,output='sos'),audio[:,0])
        streams.append(signal.hilbert(y))
    centers=np.arange(12000,132000,96);result=np.empty((len(centers),len(harmonics)),complex)
    phasor=phi**int(harmonics[0]);middle=len(kernel)//2
    for index,(m,b) in enumerate(zip(harmonics,groups)):
        if index:phasor*=phi
        demodulated=streams[b]*phasor.conj()/np.sqrt(q[:,b])
        filtered=signal.fftconvolve(demodulated,kernel)
        result[:,index]=filtered[centers+middle]
    rate=np.diff(np.unwrap(np.angle(phi[12000:-12000])))*48000/(2*np.pi)
    return result,dict(coordinate_frequency_min=float(rate.min()),coordinate_frequency_max=float(rate.max()),
        highest_actual_carrier_frequency=float(rate.max()*harmonics[-1]),source_centers=centers.tolist())

"""TRAIN-only phase-conditioned relative shape; no recorded timeline in profile."""
import numpy as np
from scipy import signal
from idle_phase_difference_v1.features import matrix
from idle_positive_power_v1.model import fit,predict,average,assess,bounds
from .split import split,response

BANDS=[[1200,2200],[2200,4000],[4000,8000],[8000,14000]]


def observe(audio,z):
    streams=[];sos=[]
    for band in BANDS:
        sections=signal.butter(4,band,btype='bandpass',fs=48000,output='sos')
        y=signal.sosfilt(sections,audio[:,0]);lo,hi=split(y,sum(band)/2)
        streams.extend((lo,hi));sos.append(sections)
    filtered=np.asarray(streams).T[12000:-12000]
    return matrix(z,hop=1),filtered**2,np.asarray(sos),filtered


def compile_model(feature,power,profile):
    model=fit(feature,power)
    if not(model['converged'] and model['full_rank'] and model['bounds']['finite_normal_bounds']):
        raise ValueError('Positive conditional branch fit failed; no widening/retry')
    beta=np.asarray(model['coefficients']);delta=beta[:,0::2]-beta[:,1::2]
    center=delta[0]+feature.mean(axis=0)@delta[1:];delta[0]-=center
    scope=bounds(delta)
    if not scope['finite_normal_bounds']:raise ValueError('Unrepresentable conditional shape')
    responses=[];effective=[]
    for kernel,band in zip(profile['kernels'][2:],BANDS):
        info,h=response(kernel,sum(band)/2);responses.append(info);effective.append(h)
    shape=dict(schema='vsl.phase-conditioned-resonant-shape/1',coefficients=delta.tolist(),
        bands_hz=BANDS,branches=responses,delta_bounds=scope,source_train_mean_delta_removed=center.tolist(),
        relative_power_proxy=True,recorded_PCM_or_phase_trajectory=False,
        scope='Acoustic relative shape law on existing source streams, not physical source separation or RPM')
    return shape,model,np.array(effective)


def assess_model(model,feature,power):
    target=average(power)/model['reference_power']
    predicted=average(predict(model,feature))
    return assess(target,predicted)

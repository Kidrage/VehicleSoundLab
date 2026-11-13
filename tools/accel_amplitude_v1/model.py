"""Train-only acoustic-coordinate amplitude laws, independent of engine IDs."""
import numpy as np


def compile_model(coordinate,amplitude,frequency,ratio,minimum_span):
    x=np.asarray(coordinate,dtype=float);a=np.asarray(amplitude,dtype=float)
    if x.ndim!=1 or a.shape!=(len(x),2) or not np.isfinite(x).all() or not np.isfinite(a).all() or np.any(a<=0):
        raise ValueError('Finite coordinates and positive stereo magnitudes required')
    if len(x)<3 or np.ptp(x)<minimum_span:return None
    y=np.log(a);xc=x-x.mean();yc=y-y.mean(axis=0)
    slope=(xc[:,None]*yc).sum(axis=0)/np.dot(xc,xc)
    return dict(count=len(x),coordinate_mean=float(x.mean()),coordinate_min=float(x.min()),coordinate_max=float(x.max()),
        log_amplitude_mean_LR=y.mean(axis=0).tolist(),slope_LR=slope.tolist(),
        RMS_amplitude_LR=np.sqrt(np.mean(a*a,axis=0)).tolist(),frequency_at_ratio1_hz=float(np.median(np.asarray(frequency)/ratio)))


def predict(model,coordinate):
    mean=np.asarray(model['log_amplitude_mean_LR']);slope=np.asarray(model['slope_LR'])
    return dict(RMS=np.asarray(model['RMS_amplitude_LR']),geometric=np.exp(mean),
        log_linear=np.exp(mean+slope*(coordinate-model['coordinate_mean'])))


def train_rows(rows,reference):
    return [(row['tile'],row['ratio'],line) for row in rows if row['guide_supported']
            for line in row['lines'] if line['reference_index']==reference and line['eligible']]

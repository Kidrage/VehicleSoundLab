"""Explicit target-plus-context objective; no per-channel reweighting."""
import numpy as np
from observer_complete_v1.synthesis import WaveSynthesis
from observer_supported_v1.metric import SupportedMetric
from observer_supported_v1.fit import SupportedSystem
from waveform_stream_v1.shared import SharedSupportedGeometry
from .metric import extend, nodes


def build(audio,target,positions,orders,scale):
    audio,target = np.asarray(audio),np.asarray(target)
    if (audio.ndim!=2 or audio.shape[1]!=2 or np.iscomplexobj(audio) or np.iscomplexobj(target)
            or target.shape!=(len(audio)-4096,2)
            or len(target)<4096 or not np.isfinite(audio).all()
            or not np.array_equal(audio[2048:-2048],target)):
        raise ValueError('Complete independent stereo context and exact original target required')
    positions = np.asarray(positions)
    extended = nodes(positions,len(audio))
    orders,scale = np.asarray(orders),np.asarray(scale)
    if (orders.ndim!=1 or not len(orders) or np.iscomplexobj(orders) or not np.isfinite(orders).all()
            or np.any(orders!=orders.astype(int))
            or np.any((orders<1)|(orders>511)) or len(np.unique(orders))!=len(orders)
            or scale.shape!=(len(orders),1) or np.iscomplexobj(scale) or not np.isfinite(scale).all() or np.any(scale<=0)):
        raise ValueError('Complete original orders and positive shared source scales required')
    reference = SupportedMetric(target,64.)
    metric = extend(reference,len(audio))
    synthesis = WaveSynthesis(len(audio),extended,orders,2)
    system = SupportedSystem(synthesis,scale,metric)
    shared = SharedSupportedGeometry(system)
    if not np.array_equal(system.D.toarray()[8:-8,8:-8],SupportedSystem(
            WaveSynthesis(len(target),positions,orders,2),scale,reference).D.toarray()):
        raise ArithmeticError('Original interior curvature rows changed')
    return system,shared,reference

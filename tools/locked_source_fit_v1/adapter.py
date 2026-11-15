"""Calibrate the metric on legacy data while fitting a distinct new source."""
import numpy as np
from observer_complete_v1.synthesis import WaveSynthesis
from observer_supported_v1.metric import SupportedMetric
from observer_supported_v1.fit import SupportedSystem
from waveform_stream_v1.shared import SharedSupportedGeometry
from waveform_file_real_v1.metric import extend, nodes


def build(audio, target, metric_target, positions, orders, scale):
    audio, target, metric_target = map(np.asarray, (audio, target, metric_target))
    if (audio.ndim != 2 or audio.shape[1] != 2 or len(audio) < 8192
            or any(np.iscomplexobj(v) or not np.isfinite(v).all() for v in (audio, target, metric_target))
            or target.shape != (len(audio)-4096, 2) or metric_target.shape != target.shape
            or not np.array_equal(audio[2048:-2048], target)):
        raise ValueError('Complete finite stereo, exact new target and explicit legacy metric_target required')
    orders, scale = np.asarray(orders), np.asarray(scale)
    if (orders.ndim != 1 or not len(orders) or np.iscomplexobj(orders) or not np.isfinite(orders).all()
            or np.any(orders != orders.astype(int)) or np.any((orders < 1) | (orders > 511))
            or len(np.unique(orders)) != len(orders) or scale.shape != (len(orders), 1)
            or np.iscomplexobj(scale) or not np.isfinite(scale).all() or np.any(scale <= 0)):
        raise ValueError('Unchanged complete original orders and positive shared scales required')
    expanded = nodes(np.asarray(positions), len(audio))
    reference = SupportedMetric(metric_target, 64.)
    metric = extend(reference, len(audio))
    synthesis = WaveSynthesis(len(audio), expanded, orders, 2)
    system = SupportedSystem(synthesis, scale, metric)
    shared = SharedSupportedGeometry(system)
    return system, shared, reference

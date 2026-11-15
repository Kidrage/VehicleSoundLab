"""Independent complete equations with legacy calibration and new-data RHS."""
import numpy as np
from observer_complete_v1.audit_oracle import full_frame, curvature
from observer_supported_v1.audit_oracle import metric
from observer_supported_v1.full_oracle import FullOracle
from waveform_file_real_v1.audit_oracle import mono_matrix, qr_solve


def make(audio, metric_target, positions, orders, scale):
    old = metric(metric_target, 64.)
    rows, coverage = full_frame(audio)
    starts = np.arange(-3840, len(audio), 256)
    keep = (starts >= 0) & (starts+4096 <= len(audio))
    window = .5-.5*np.cos(2*np.pi*np.arange(4096)/4096)
    supported = np.zeros(len(audio))
    for first in starts[keep]: supported[first:first+4096] += window**2
    result = object.__new__(FullOracle)
    result.audio, result.positions, result.orders, result.scale = audio, positions, orders, scale
    result.shape = (len(positions), len(orders), 2)
    result.profile = dict(old, rows=rows[keep]*old['amplitude'], keep=keep,
        full_coverage=coverage, time_coverage=old['amplitude']**2*supported/coverage)
    result.D = curvature(positions)
    result.R = .001*result.D.T@result.D+.000001*np.eye(len(positions))
    result.wave_size = audio.size
    result.row_shape = result.profile['rows'].shape
    result.data_size = audio.size+2*int(np.prod(result.row_shape))
    return result, old

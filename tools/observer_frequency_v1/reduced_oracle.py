"""Independent integer-cycle scalar trigonometry with reduced exact angles.

Large-angle sin/cos roundoff is avoidable here: integer orders on a 1024-point
cycle admit an exact modular phase index. This is an audit oracle, not DSP code.
"""
from functools import lru_cache
import numpy as np
from observer_complete_v1.audit_oracle import hats


@lru_cache(maxsize=8)
def carrier_table(order_tuple):
    ids = (np.arange(1024)[:, None]*np.array(order_tuple)[None, :]) % 1024
    pi = np.arccos(np.longdouble(-1))
    angle = ids.astype(np.longdouble)*(2*pi/1024)
    return np.cos(angle).astype(float)+1j*np.sin(angle).astype(float)


def synthesize(nodes, positions, orders, frames):
    table = carrier_table(tuple(int(k) for k in orders))[np.arange(frames) % 1024]
    audio = np.zeros((frames, nodes.shape[-1]), dtype=np.longdouble)
    for h in range(len(orders)):
        for c in range(nodes.shape[-1]):
            re = np.interp(np.arange(frames), positions, nodes[:, h, c].real)
            im = np.interp(np.arange(frames), positions, nodes[:, h, c].imag)
            audio[:, c] += re.astype(np.longdouble)*table[:, h].real-im.astype(np.longdouble)*table[:, h].imag
    return audio.astype(float)


def adjoint(wave, positions, orders):
    table = carrier_table(tuple(int(k) for k in orders))[np.arange(len(wave)) % 1024].conj()
    values = (wave[:, None, :]*table[:, :, None]).reshape(len(wave), -1)
    return (hats(positions, len(wave))@values).reshape(len(positions), len(orders), wave.shape[-1])

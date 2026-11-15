"""Block-persistent circular lift; held-common synthesis is a new time law."""
from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class LiftState:
    previous_raw: np.ndarray
    winding: np.ndarray


def lift_block(raw, state=None):
    """Lift each column by nearest successive phase steps, preserving state.

    This preserves the sampled circular relative phase, not absolute L/R phase
    or its common/relative joint distribution. Nyquist/half-turn ambiguity is
    reported rather than interpreted as physical phase velocity.
    """
    raw = np.asarray(raw, dtype=np.float64)
    if raw.ndim != 2 or not len(raw) or not np.isfinite(raw).all():
        raise ValueError('Expected a nonempty finite sample-by-partial matrix')
    if state is None:
        difference = np.vstack([np.zeros(raw.shape[1]), np.diff(raw, axis=0)])
        initial = np.zeros(raw.shape[1], dtype=np.int64)
    else:
        if state.previous_raw.shape != raw.shape[1:] or state.winding.shape != raw.shape[1:]:
            raise ValueError('Lift state has the wrong partial count')
        difference = np.diff(np.vstack([state.previous_raw, raw]), axis=0)
        initial = state.winding
    turns = difference/(2*np.pi)
    if np.max(abs(turns)) > 2**40:
        raise ValueError('Phase increments exceed exact winding accounting range')
    increments = np.rint(turns).astype(np.int64)
    winding = initial + np.cumsum(increments, axis=0, dtype=np.int64)
    lifted = raw - (2*np.pi)*winding
    half_turn = abs(abs(turns-np.rint(turns))-.5) <= 16*np.finfo(float).eps
    result = dict(increments=increments, winding=winding, half_turn_ambiguous=half_turn)
    return lifted, LiftState(raw[-1].copy(), winding[-1].copy()), result

"""Exact band solve then native correction with explicit factor lifetimes."""
import gc
import hashlib
import weakref
from waveform_stream_v1.solver import solve
from .native_inverse import NativeNormalInverse
from .correct import refine


def owner(array):
    while hasattr(array.base, 'shape'):
        array=array.base
    return array


def solve_corrected(forward,adjoint,prior,metric_factory,target,metric_action,ledger,block=16):
    metric=metric_factory()
    base,base_info=solve(forward,adjoint,prior,metric,target,ledger,block)
    ledger.snapshot('pipeline.base_solve_complete')
    refs=dict(metric=weakref.ref(owner(metric.bands)),
              graph=weakref.ref(owner(base['graph_reflectors'])),
              graph_T=weakref.ref(owner(base['graph_R'])))
    keep={n:base[n] for n in ('x_raw','q','z','wave_model_residual')}
    initial={n:base[n] for n in ('q','z','wave_model_residual')}
    source_sha=hashlib.sha256(memoryview(keep['x_raw'].ravel(order='F'))).hexdigest()
    del base,metric
    gc.collect()
    released={n:ref() is None for n,ref in refs.items()}
    if not all(released.values()):raise RuntimeError(('Old base factor retained',released))
    ledger.snapshot('pipeline.old_metric_graph_T_released')
    source_ref=weakref.ref(owner(keep['x_raw']))
    inverse=NativeNormalInverse(keep['x_raw'],ledger,block)
    del keep['x_raw']
    gc.collect()
    if source_ref() is not None:raise RuntimeError('Old X retained after inverse construction')
    ledger.snapshot('pipeline.source_QR_released')
    corrected=refine(forward,adjoint,prior,metric_action,keep,inverse)
    ledger.snapshot('pipeline.original_correction_complete')
    return corrected,inverse,dict(base_solver=base_info,released_before_new_factors=released,
        source_QR_released_before_correction=True,source_QR_sha256=source_sha,
        native_triangle_has_no_square_copy=True),initial

"""Native base graph, real factor lifetimes and early source release."""
import gc
import weakref
from waveform_stream_v1.solver import solve
from waveform_correction_v1.pipeline import owner
from waveform_correction_v1.correct import refine
from .inverse import OwnedNativeInverse


def solve_owned_corrected(forward,adjoint,prior,metric_factory,target,metric_action,ledger,block=16):
    metric=metric_factory()
    base,base_info=solve(forward,adjoint,prior,metric,target,ledger,block,triangle_backend='native')
    ledger.snapshot('pipeline.base_solve_complete')
    if base['graph_R'] is not None or base['graph_triangle_raw'] is not owner(base['graph_reflectors']):
        raise RuntimeError('Native base graph unexpectedly has a copied triangle')
    refs=dict(metric=weakref.ref(owner(metric.bands)),
              graph=weakref.ref(owner(base['graph_reflectors'])))
    source_ref=weakref.ref(owner(base['x_raw']))
    holder=[base['x_raw']]
    keep={n:base[n] for n in ('q','z','wave_model_residual')}
    initial=dict(keep)
    del base,metric
    gc.collect()
    released={n:ref() is None for n,ref in refs.items()}
    if not all(released.values()):raise RuntimeError(('Old base factor retained',released))
    ledger.snapshot('pipeline.old_metric_graph_T_released')
    inverse=OwnedNativeInverse(holder,ledger,block)
    if holder or source_ref() is not None:raise RuntimeError('Owned source X did not release')
    ledger.snapshot('pipeline.source_QR_released')
    corrected=refine(forward,adjoint,prior,metric_action,keep,inverse)
    ledger.snapshot('pipeline.original_correction_complete')
    return corrected,inverse,dict(base_solver=base_info,released_before_new_factors=released,
        source_QR_released_before_inner=True,source_QR_released_before_correction=True,
        source_QR_sha256=inverse.source_sha,native_triangle_has_no_square_copy=True,
        base_graph_has_no_square_copy=True),initial

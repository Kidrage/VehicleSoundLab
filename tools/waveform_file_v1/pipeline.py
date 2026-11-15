"""Complete file graph and original two-step correction, default RAM untouched."""
import gc
import weakref
from waveform_correction_v1.correct import refine
from waveform_correction_v1.pipeline import owner
from .solver import solve_file
from .inverse import FileNormalInverse


def solve_corrected_file(forward, adjoint, prior, metric_factory, target, metric_action, directory, ledger, block):
    metric = metric_factory()
    metric_ref = weakref.ref(owner(metric.bands))
    base, source, graph, base_info = solve_file(forward, prior, metric, target, directory, ledger, block)
    initial = {name:base[name] for name in ('q', 'z', 'wave_model_residual')}
    graph.raw.close()
    graph_info = graph.report()
    del metric
    gc.collect()
    if metric_ref() is not None:
        raise RuntimeError('Complete band metric still retained before inverse factors')
    ledger.snapshot('filePipeline.metric_and_base_graph_released')
    inverse = FileNormalInverse(source)
    source.raw.close()
    source_info = source.report()
    corrected = refine(forward, adjoint, prior, metric_action, initial, inverse)
    ledger.snapshot('filePipeline.original_two_corrections_complete')
    return corrected, inverse, dict(base_solver=base_info, source=source_info, graph=graph_info,
        complete_metric_released_before_inverse=True, source_file_closed_before_correction=True,
        complete_file_factorization=True, no_square_T_or_explicit_Q=True), initial, source.tau

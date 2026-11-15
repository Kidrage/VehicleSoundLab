"""Full-known file pipeline with original base guard and actual metric release."""
import gc
import weakref
from waveform_correction_v1.pipeline import owner
from waveform_correction_v1.correct import refine
from waveform_file_v1.solver import solve_file
from waveform_file_v1.inverse import FileNormalInverse
from .base_guard import inspect


def solve_full(shared, metric_factory, audio, metric_action, directory, ledger, block):
    metric = metric_factory()
    ref = weakref.ref(owner(metric.bands))
    base, source, graph, info = solve_file(shared.forward, shared.prior, metric, audio, directory, ledger, block)
    info.update(inspect(metric, info, base, audio, shared.forward, shared.adjoint, shared.prior, ledger))
    initial = {name:base[name] for name in ('q', 'z', 'wave_model_residual')}
    graph.raw.close()
    graph_info, graph_tau = graph.report(), graph.tau
    del metric
    gc.collect()
    if ref() is not None:
        raise RuntimeError('Original band root was not released before inverse file factors')
    ledger.snapshot('fullPipeline.metric_and_graph_released')
    inverse = FileNormalInverse(source)
    source.raw.close()
    source_info, source_tau = source.report(), source.tau
    values = refine(shared.forward, shared.adjoint, shared.prior, metric_action, initial, inverse)
    ledger.snapshot('fullPipeline.original_two_corrections_complete')
    return values, inverse, dict(base_solver=info, source=source_info, graph=graph_info,
        complete_metric_released_before_inverse=True, source_file_closed_before_correction=True,
        complete_file_factorization=True, no_square_T_or_explicit_Q=True), initial, dict(file_x_tau=source_tau, file_graph_tau=graph_tau)

"""Complete support counts and allocations, without compiling full source blocks."""
import numpy as np


def describe(geometry,column_batch=32,cache_bytes=64*1024**2):
    g=geometry;wave=[];spectrum=[]
    for first in range(0,g.frames,256):
        last=min(first+256,g.frames);columns=len(g.active(first,last))
        wave.append(dict(first=first,rows=last-first,columns=columns,matrix_bytes=(last-first)*columns*8))
    for index,first in enumerate(g.starts):
        columns=len(g.active(int(first),int(first)+4096))
        spectrum.append(dict(index=index,first=int(first),rows=4098,columns=columns,matrix_bytes=4098*columns*8))
    source_bytes=sum(v.nbytes for v in (g.hats,g.carriers,g.weights,g.positions,g.orders,g.scale,g.window,g.normalizer,g.endpoint))
    spectral_bytes=sum(v['matrix_bytes'] for v in spectrum);wave_bytes=sum(v['matrix_bytes'] for v in wave)
    max_block=max(v['matrix_bytes'] for v in spectrum)
    # Conservative authored-array budget, not a whole-process or solver bound.
    scratch=4096*column_batch*8*8+4098*column_batch*16*4
    vectors=16*(g.full_rows+g.size)*8
    return dict(frames=g.frames,nodes=len(g.positions),orders=len(g.orders),real_unknowns=g.size,
        full_data_rows=g.full_rows,full_supported_windows=len(g.starts),target_supported_windows=len(g.target_slots),
        full_dense_bytes=g.full_rows*g.size*8,one_channel_global_dense_bytes=(g.full_rows//2)*g.mono_size*8,
        shared_wave_blocks=wave,shared_spectral_blocks=spectrum,shared_spectral_payload_bytes=spectral_bytes,
        shared_wave_payload_bytes=wave_bytes,maximum_spectral_block_bytes=max_block,
        source_geometry_bytes=source_bytes,FFT_column_batch=column_batch,bounded_cache_bytes=cache_bytes,
        estimated_authored_array_budget_bytes=source_bytes+cache_bytes+max_block+scratch+vectors,
        one_forward_matrix_products=2*(spectral_bytes+wave_bytes)//8,
        one_adjoint_matrix_products=2*(spectral_bytes+wave_bytes)//8,
        spectral_column_FFTs_per_uncached_action=sum(v['columns'] for v in spectrum),
        no_full_dense_matrix_or_actual_factor_allocation=True,
        resource_bound_does_not_include_solver_or_Python_BLAS_allocator_or_timing=True)

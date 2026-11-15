"""Independent file descriptors, native argument records and lifetime arithmetic.

No production FileMatrix, QR, triangle, resource-preflight or solver imports.
Hashes stream complete factor files; they are outside explicit panel I/O counters.
"""
from collections import Counter
import math
from pathlib import Path
from research_archive_v1 import sha


def inspect(source, study):
    N, M, H, B = 12289, 49, 288, 1024
    n, k = 2*M*H, N
    descriptor = source['pipeline']
    inverse = source['inverse_info']
    assert descriptor['complete_metric_released_before_inverse']
    assert descriptor['source_file_closed_before_correction']
    assert descriptor['complete_file_factorization'] and descriptor['no_square_T_or_explicit_Q']
    assert not inverse['separate_square_T_allocated'] and not inverse['explicit_full_Q']
    assert not inverse['normal_equation_factorization'] and not inverse['subtractive_Woodbury']
    assert inverse['source_columns'] == n and inverse['retained_inner_directions'] == k
    assert inverse['identity_complement_directions'] == n-k
    base = source['solver']
    assert base['waveform_rows'] == N and base['source_columns'] == n and base['RHS'] == 2
    assert base['retained_QR_directions'] == k and base['block'] == B
    for flag in ('complete_source_streamed', 'source_whitening_rows_streamed',
                 'no_dense_X_or_graph_or_square_T_or_full_Q',
                 'no_order_node_rank_rate_context_or_scale_reduction', 'metric_root_shares_input'):
        assert base[flag]
    resources = source['resources']
    events, stores = resources['events'], resources['storage_bytes']
    arrays = [x for x in events if x['event'] == 'array']
    snapshots = [x for x in events if x['event'] == 'snapshot']
    forbidden = {(N,n), (k+n,k), (n,k), (2*k,k), (k,k)}
    for x in arrays:
        assert x['bytes'] == 8*math.prod(x['shape'])
        assert x['backing_bytes'] == stores[x['storage']] and x['bytes'] <= x['backing_bytes']
        assert x['dtype'] == 'float64' and tuple(x['shape']) not in forbidden
        assert not x['name'].startswith('audit_only.full_file_export')
    for x in snapshots:
        ids = x['live_storages']
        assert len(ids) == len(set(ids))
        assert x['tracked_live_backing_bytes'] == sum(stores[j] for j in ids)
    assert max(x['tracked_live_backing_bytes'] for x in snapshots) == resources['max_tracked_live_backing_bytes']
    calls = []
    factors = []
    expected = ((descriptor['source'], (N,n), 'source.bin'),
                (descriptor['graph'], (k+n,k), 'graph.bin'),
                (inverse['right'], (n,k), 'right.bin'),
                (inverse['inner'], (2*k,k), 'inner.bin'))
    for info, shape, filename in expected:
        disk = info['file']
        assert (info['rows'], info['columns']) == shape == tuple(disk['shape'])
        assert info['retained_directions'] == min(shape) and info['block'] == B
        assert not info['explicit_full_Q'] and info['full_R_and_reflectors_on_disk']
        assert disk['dtype'] == 'float64' and disk['order'] == 'F'
        assert disk['closed'] and not disk['mapped'] and disk['block'] == B
        assert disk['file_bytes'] == disk['declared_bytes'] == 8*math.prod(shape)
        capacity = 8*max(shape)*B
        assert disk['panel_capacity_bytes'] == capacity
        assert 0 < disk['max_read_buffer_bytes'] <= capacity
        assert 0 < disk['max_write_panel_bytes'] <= capacity
        path = Path(disk['path'])
        assert path.resolve() == (study/'factors'/filename).resolve()
        assert path.stat().st_size == disk['file_bytes'] and sha(path) == disk['sha256']
        assert disk['write_bytes'] >= disk['file_bytes'] and disk['read_bytes'] > 0
        geqrf = [c for c in info['native_calls'] if c['kernel'] == 'geqrf']
        assert len(geqrf) == (min(shape)+B-1)//B
        for index, c in enumerate(geqrf):
            start = index*B
            assert c['panel_shape'] == [shape[0]-start, min(B,min(shape)-start)]
        for call in info['native_calls']:
            calls.append(call)
            assert call['kernel'] in ('geqrf', 'ormqr_T', 'ormqr_N', 'trtrs_T', 'trtrs_N')
            assert call['panel_owned'] and call['panel_Fortran'] and call['output_aliases_input']
            assert not call['whole_mapped_matrix']
            assert 0 < call['panel_shape'][1] <= B
            assert call['panel_bytes'] == 8*math.prod(call['panel_shape']) <= capacity
            if call['target_shape'] is not None:
                assert call['target_owned'] and call['target_Fortran']
                assert 0 < call['target_shape'][1] <= B
                assert call['target_bytes'] == 8*math.prod(call['target_shape']) <= capacity
            assert call['lwork'] >= 0
        factors.append(dict(name=filename, shape=list(shape), bytes=disk['file_bytes'],
            sha256=disk['sha256'], read_bytes=disk['read_bytes'], write_bytes=disk['write_bytes'],
            max_native_panel_bytes=max(c['panel_bytes'] for c in info['native_calls']),
            max_native_target_bytes=max(c['target_bytes'] for c in info['native_calls']),
            max_native_workspace_bytes=max(8*c['lwork'] for c in info['native_calls']),
            native_call_count=len(info['native_calls'])))
    # Native workspace records must match the actual registered allocations,
    # including repeated equal-size workspaces rather than just set membership.
    for kernel, label in (('geqrf', 'fileQR.geqrf.work'), ('ormqr', 'fileQR.ormqr.work')):
        declared = Counter(8*c['lwork'] for c in calls if c['kernel'].startswith(kernel))
        actual = Counter(x['bytes'] for x in arrays if x['name'] == label)
        assert declared == actual, (kernel, declared, actual)
    for kernel, label, key in (('geqrf', 'fileQR.geqrf.raw', 'panel_shape'),
                              ('ormqr', 'fileQR.ormqr.result', 'target_shape'),
                              ('trtrs', 'fileTriangle.diagonal_result', 'target_shape')):
        declared = Counter(tuple(c[key]) for c in calls if c['kernel'].startswith(kernel))
        actual = Counter(tuple(x['shape']) for x in arrays if x['name'] == label)
        assert declared == actual
    metric_ids = {x['storage'] for x in arrays if x['name'] in ('wave_metric.input','wave_metric.L_banded')}
    assert len(metric_ids) == 1
    assert any(x['name'] == 'wave_metric.L_banded' and x['shape'] == [4096,N] for x in arrays)
    release = next(i for i,x in enumerate(events) if x.get('phase') == 'fullPipeline.metric_and_graph_released')
    for x in events[release:]:
        if x['event'] == 'snapshot': assert not metric_ids.intersection(x['live_storages'])
    assert not any(x.get('name') == 'fileQR.tau.right.bin' for x in events[:release])
    assert source['no_full_factor_arrays_in_capture']
    # Recompute every original phase formula without importing producer code.
    band = 8*4096*N
    column, row = 8*N*B, 8*n*B
    phases = dict(source_columns=band+2*column, row_whitening=band+4*row,
        source_QR=band+2*column, graph_transpose=band+8*k*B+2*row,
        graph_QR=band+2*8*(k+n)*B, inverse_right=2*row,
        inverse_inner=2*8*(2*k)*B,
        diagonal_and_update=2*8*B*B+8*(N+n+k)*4)
    p = source['resource_preflight']
    assert p['major_phase_panel_arithmetic'] == phases
    assert p['resident_misc_allowance'] == 128*1024**2
    assert p['main_phase_array_allowance'] == max(phases.values())+128*1024**2
    assert p['native_temporary_allowance'] == 3*1024**3//2 and p['headroom_guard'] == 3*1024**3
    assert p['required_available'] == p['main_phase_array_allowance']+p['native_temporary_allowance']+p['headroom_guard']
    assert p['memory_passed'] == (min(p['available_physical_bytes'],p['available_commit_bytes']) >= p['required_available'])
    disk = dict(source=8*N*n, graph=8*(k+n)*k, right=8*n*k, inner=16*k*k)
    assert p['full_factor_file_bytes'] == disk
    assert p['full_factor_disk_bytes'] == sum(disk.values()) == sum(x['bytes'] for x in factors)
    assert p['disk_output_allowance'] == p['disk_guard'] == 1024**3
    assert p['required_available_disk'] == sum(disk.values())+2*1024**3
    assert p['disk_passed'] == (p['available_disk_bytes'] >= p['required_available_disk'])
    assert p['memory_passed'] and p['disk_passed']
    return dict(all_qualified=True, factors=factors, native_calls=len(calls),
        panel_read_bytes=sum(x['read_bytes'] for x in factors),
        panel_write_bytes=sum(x['write_bytes'] for x in factors),
        factor_file_bytes=sum(x['bytes'] for x in factors),
        registered_peak_bytes=resources['max_tracked_live_backing_bytes'],
        process_memory=source['process_memory'], metric_release_verified=True,
        all_native_argument_and_workspace_records_verified=True,
        original_preflight_arithmetic_verified=True,
        no_physical_total_IO_or_unregistered_memory_bound_claim=True)

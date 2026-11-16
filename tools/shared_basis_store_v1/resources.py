"""Preflight full persistent payload and bounded reader/writer arrays."""
import shutil

from bench_shared_basis_block_v1 import available_memory
from shared_basis_operator_v1.resources import describe


def budget(g):
    original = describe(g, cache_bytes=0)
    id_bytes = sum(row['columns'] * 8 for row in original['shared_spectral_blocks'])
    payload = original['shared_spectral_payload_bytes'] + id_bytes
    headers = 4096 * 2 * len(g.starts) + 1024**2
    maximum = original['maximum_spectral_block_bytes']
    # Python holds the previous returned block until the next call returns.
    # Include both arrays, ID arrays, finite-check scratch and extra vectors.
    array_bytes = (original['estimated_authored_array_budget_bytes'] + maximum
                   + maximum//8 + id_bytes + 16*(g.full_rows+g.size)*8)
    return dict(
        spectral_payload_bytes=original['shared_spectral_payload_bytes'],
        id_payload_bytes=id_bytes, payload_bytes=payload,
        file_and_manifest_overhead_allowance_bytes=headers,
        disk_bytes_including_temporary_allowance=payload+headers+maximum,
        estimated_authored_array_bytes=array_bytes,
        process_library_reserve_bytes=2*1024**3, disk_reserve_bytes=2*1024**3,
        maximum_block_bytes=maximum, spectral_blocks=len(g.starts),
        no_whole_solver_memory_or_timing_bound=True)


def preflight(g, parent, *, disk_cap, array_cap):
    if type(disk_cap) is not int or type(array_cap) is not int or min(disk_cap, array_cap) <= 0:
        raise ValueError('Explicit positive integer resource caps required')
    plan = budget(g)
    if (plan['disk_bytes_including_temporary_allowance'] > disk_cap
            or plan['estimated_authored_array_bytes'] > array_cap):
        raise ValueError('Declared store resource cap exceeded')
    disk_free = shutil.disk_usage(parent).free
    memory_free = available_memory()
    if disk_free < plan['disk_bytes_including_temporary_allowance'] + plan['disk_reserve_bytes']:
        raise ValueError('Insufficient disk space including reserve')
    if memory_free < plan['estimated_authored_array_bytes'] + plan['process_library_reserve_bytes']:
        raise ValueError('Insufficient physical memory including reserve')
    return dict(plan, disk_cap_bytes=disk_cap, array_cap_bytes=array_cap,
                free_disk_bytes=disk_free, available_physical_bytes=memory_free)

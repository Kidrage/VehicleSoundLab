"""Compile once and atomically publish an immutable complete synthetic store."""
import os
from pathlib import Path
import uuid

import numpy as np
from research_archive_v1 import save, sha
from shared_basis_operator_v1.compiler import Compiler
from .identity import SCHEMA, array_digest, digest, geometry_binding
from .resources import preflight


def write_array(path, value):
    with path.open('xb') as stream:
        np.save(stream, value, allow_pickle=False)
        stream.flush()
        os.fsync(stream.fileno())
    return dict(file=path.name, bytes=path.stat().st_size, file_sha256=sha(path), **array_digest(value))


def build(root, g, spec, *, disk_cap, array_cap, progress=None):
    root = Path(root)
    if root.exists() or spec['schema'] != SCHEMA or spec['domain'] != 'known-synthetic-only':
        raise ValueError('Fresh synthetic store destination required; no overwrite or implicit resume')
    if any(spec.get(key) != value for key, value in geometry_binding(g).items()):
        raise ValueError('Store specification does not bind the supplied geometry')
    checked = preflight(g, root.parent, disk_cap=disk_cap, array_cap=array_cap)
    pending = root.with_name(root.name+'.pending.'+uuid.uuid4().hex)
    pending.mkdir(exist_ok=False)
    compiler = Compiler(g, cache_bytes=0)
    rows = []
    # An interrupted pending directory is intentionally retained, never opened
    # as a complete cache and never silently restarted by this builder.
    for index in range(len(g.starts)):
        ids, matrix = compiler.spectral(index)
        if ids.dtype != np.dtype('int64') or matrix.dtype != np.dtype('float64'):
            raise ValueError('Canonical 64-bit block storage required')
        if not np.isfinite(matrix).all():
            raise ValueError('Nonfinite compiled block')
        ids_info = write_array(pending/('block_%03d_ids.npy' % index), ids)
        matrix_info = write_array(pending/('block_%03d_matrix.npy' % index), matrix)
        if ids_info['bytes'] > ids.nbytes+4096 or matrix_info['bytes'] > matrix.nbytes+4096:
            raise ValueError('NPY overhead exceeded preflight allowance')
        rows.append(dict(index=index, first=int(g.starts[index]), ids=ids_info, matrix=matrix_info))
        del ids, matrix
        if progress:
            progress(index+1, len(g.starts))
    manifest = dict(schema=SCHEMA, complete=True, identity=spec,
                    identity_sha256=digest(spec), blocks=rows, preflight=checked)
    temporary_manifest = pending/'manifest.pending.json'
    save(temporary_manifest, manifest)
    # Windows _commit requires a writable descriptor, even after save closed
    # and flushed the file. Read-only fsync raises EBADF on this host.
    with temporary_manifest.open('r+b') as stream:
        os.fsync(stream.fileno())
    temporary_manifest.rename(pending/'manifest.json')
    if sum(p.stat().st_size for p in pending.iterdir()) > checked['disk_bytes_including_temporary_allowance']:
        raise ValueError('Published payload exceeded preflight bound')
    # rename to a new directory on the same volume; no replace semantics.
    pending.rename(root)
    return dict(root=str(root), manifest_sha256=sha(root/'manifest.json'),
                identity_sha256=digest(spec), blocks=len(rows), preflight=checked,
                stored_bytes=sum(p.stat().st_size for p in root.iterdir()))

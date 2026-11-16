"""Canonical geometry, calibration, compiler and runtime bindings."""
import hashlib
import json
from pathlib import Path
import platform
import sys

import numpy as np
from research_archive_v1 import sha


SCHEMA = 'vsl.synthetic-shared-block-store/1'
COMPILATION_SOURCES = (
    'tools/shared_basis_operator_v1/geometry.py',
    'tools/shared_basis_operator_v1/compiler.py',
    'tools/shared_basis_operator_v1/operator.py',
    'tools/shared_basis_operator_v1/resources.py',
    'tools/constrained_source_operator_v1/prior.py',
    'tools/observer_complete_v1/frame.py',
)


def digest(value):
    encoded = json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    return hashlib.sha256(encoded).hexdigest()


def array_digest(value):
    value = np.ascontiguousarray(value)
    return dict(shape=list(value.shape), dtype=value.dtype.str,
                sha256=hashlib.sha256(memoryview(value).cast('B')).hexdigest())


def geometry_binding(g):
    arrays = ('positions', 'orders', 'scale', 'carriers', 'weights', 'hats',
              'window', 'normalizer', 'endpoint', 'starts', 'target_slots', 'bands')
    return dict(
        frames=g.frames, unknowns=g.size, full_rows=g.full_rows,
        amplitude_hex=g.amplitude.hex(), sigma_hex=g.sigma.hex(),
        arrays={name: array_digest(getattr(g, name)) for name in arrays})


def specification(g, repo):
    from numpy.fft import _pocketfft_umath
    from numpy._core import _multiarray_umath
    return dict(
        schema=SCHEMA, domain='known-synthetic-only', method='vsl.shared-rounded-source-observation/1',
        **geometry_binding(g),
        sources={name: sha(repo/name) for name in COMPILATION_SOURCES},
        runtime=dict(python=sys.version, implementation=platform.python_implementation(),
                     executable_sha256=sha(sys.executable), numpy=np.__version__,
                     byteorder=sys.byteorder,
                     fft_native_sha256=sha(Path(_pocketfft_umath.__file__)),
                     array_native_sha256=sha(Path(_multiarray_umath.__file__))))

"""Combine terminal new-method mathematical admission with the native bridge."""
from pathlib import Path
import numpy as np
from research_archive_v1 import load
from .input import terminal
from .native_reference import bind_reference


def bind(case, math_audit, *, repo, workspace, native_study, native_audit,
         known_study, known_audit):
    z, source = terminal(case, math_audit, repo=repo, known=False)
    info = load(Path(case)/'report.json')
    native, binding = bind_reference(z, Path(case).name, info['prepared_file'], info['prepared_sha256'],
        repo=repo, workspace=workspace, native_study=native_study, native_audit=native_audit,
        known_study=known_study, known_audit=known_audit)
    if z['fitted'].shape != (len(z['positions']), 288, 2) or not np.isfinite(z['fitted']).all():
        raise ValueError('Finite complete288-order stereo fitted coefficients required')
    binding['inputs'].update(source['inputs'])
    return z, native, dict(source=source, **binding)

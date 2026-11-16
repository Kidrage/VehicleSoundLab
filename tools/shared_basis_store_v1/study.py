"""Evidence capture shared by synthetic storage and full-geometry studies."""
from pathlib import Path
import shutil

from research_archive_v1 import sha


def capture(repo, out, previous, extra):
    sources = set(previous['sources']) | set(extra)
    sources.update(p.relative_to(repo).as_posix()
                   for p in (repo/'tools/shared_basis_store_v1').glob('*.py'))
    result = {}
    for name in sorted(sources):
        if name in previous['sources'] and sha(repo/name) != previous['sources'][name]:
            raise ValueError('Previously qualified source changed: '+name)
        dest = out/'exact_sources'/name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(repo/name, dest)
        result[name] = sha(dest)
    return result


def geometry_args(z, carriers):
    return (int(z['frames']), z['positions'], z['orders'], z['scale'], carriers,
            z['weights'], float(z['amplitude']), float(z['sigma']))


def load_arrays(path):
    import numpy as np
    with np.load(path, allow_pickle=False) as stream:
        return {key: stream[key] for key in stream.files}

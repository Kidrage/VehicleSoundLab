"""Read one bounded block at a time, checking its externally bound identity."""
import hashlib
from pathlib import Path

import numpy as np
from research_archive_v1 import load, sha
from .identity import SCHEMA, digest, geometry_binding


def read_array(root, info, *, shape, dtype):
    path = root/info['file']
    if path.is_symlink() or path.resolve().parent != root.resolve():
        raise ValueError('Store payload must remain inside the owned directory')
    if path.stat().st_size != info['bytes']:
        raise ValueError('Incomplete store payload')
    with path.open('rb') as stream:
        if np.lib.format.read_magic(stream) != (1, 0):
            raise ValueError('Canonical NPY version required')
        saved_shape, fortran, saved_dtype = np.lib.format.read_array_header_1_0(stream)
        offset = stream.tell()
        if saved_shape != shape or fortran or saved_dtype != dtype:
            raise ValueError('Store header does not match canonical supported block')
        count = int(np.prod(shape))
        if offset+count*dtype.itemsize != info['bytes']:
            raise ValueError('Store length does not match header')
        stream.seek(0)
        header = stream.read(offset)
        array = np.fromfile(stream, dtype=dtype, count=count).reshape(shape)
    payload = memoryview(array).cast('B')
    if hashlib.sha256(payload).hexdigest() != info['sha256']:
        raise ValueError('Corrupt store array payload')
    file_hash = hashlib.sha256(header)
    file_hash.update(payload)
    if file_hash.hexdigest() != info['file_sha256']:
        raise ValueError('Corrupt store file')
    array.flags.writeable = False
    return array


class StoredCompiler:
    def __init__(self, root, g, expected_spec, manifest_sha256):
        self.root, self.g = Path(root), g
        if any(expected_spec.get(key) != value for key, value in geometry_binding(g).items()):
            raise ValueError('Store specification does not bind the supplied geometry')
        manifest_path = self.root/'manifest.json'
        if manifest_path.is_symlink() or sha(manifest_path) != manifest_sha256:
            raise ValueError('Unbound store manifest')
        manifest = load(manifest_path)
        if (manifest.get('schema') != SCHEMA or manifest.get('complete') is not True
                or manifest.get('identity') != expected_spec
                or manifest.get('identity_sha256') != digest(expected_spec)):
            raise ValueError('Store identity mismatch or incomplete publication')
        self.blocks = manifest['blocks']
        if len(self.blocks) != len(g.starts):
            raise ValueError('Missing supported store blocks')
        files = {'manifest.json'}
        for index, block in enumerate(self.blocks):
            columns = len(g.active(int(g.starts[index]), int(g.starts[index])+4096))
            if block['index'] != index or block['first'] != int(g.starts[index]):
                raise ValueError('Store block ordering mismatch')
            for key, shape, dtype in (('ids', [columns], np.dtype('int64')),
                                      ('matrix', [4098, columns], np.dtype('float64'))):
                info = block[key]
                filename = 'block_%03d_%s.npy' % (index, key)
                payload = int(np.prod(shape))*8
                if (info['file'] != filename or info['shape'] != shape or info['dtype'] != dtype.str
                        or not payload < info['bytes'] <= payload+4096):
                    raise ValueError('Store metadata disagrees with supported geometry')
                path = self.root/filename
                if path.is_symlink() or path.stat().st_size != info['bytes']:
                    raise ValueError('Missing or incomplete supported store payload')
                files.add(filename)
        if {p.name for p in self.root.iterdir()} != files:
            raise ValueError('Unexpected or partial store contents')
        self.loaded_blocks = 0
        self.loaded_bytes = 0

    def wave(self, first, last):
        ids = self.g.active(first, last)
        return ids, self.g.columns(first, last, ids)

    def spectral(self, index):
        if type(index) is not int or not 0 <= index < len(self.blocks):
            raise ValueError('Supported integer store block index required')
        block = self.blocks[index]
        active = self.g.active(int(self.g.starts[index]), int(self.g.starts[index])+4096)
        ids = read_array(self.root, block['ids'], shape=active.shape, dtype=np.dtype('int64'))
        if not np.array_equal(ids, active):
            raise ValueError('Store support IDs differ from canonical geometry')
        matrix = read_array(self.root, block['matrix'], shape=(4098, len(ids)), dtype=np.dtype('float64'))
        self.loaded_blocks += 1
        self.loaded_bytes += block['ids']['bytes']+block['matrix']['bytes']
        return ids, matrix

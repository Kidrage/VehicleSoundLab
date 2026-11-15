"""Owned FP64 file matrices with explicit bounded reads, without mappings."""
import hashlib
from pathlib import Path
import shutil
import numpy as np


class FileMatrix:
    def __init__(self, path, shape, block, ledger):
        if (len(shape) != 2 or any(type(x) is not int or x < 1 for x in shape)
                or type(block) is not int or block < 1):
            raise ValueError('Positive integer shape and panel width required')
        self.path = Path(path)
        self.rows, self.columns = self.shape = tuple(shape)
        self.block, self.ledger = block, ledger
        self.size_bytes = 8*self.rows*self.columns
        self.buffer_limit_bytes = 8*max(self.shape)*block
        if shutil.disk_usage(self.path.parent).free < self.size_bytes + 1024**3:
            raise MemoryError('Insufficient disk space plus 1GiB file guard')
        self.stream = self.path.open('x+b', buffering=0)
        self.stream.truncate(self.size_bytes)
        self.read_bytes = self.write_bytes = self.read_calls = self.write_calls = 0
        self.max_read_buffer_bytes = self.max_write_panel_bytes = 0
        self.closed = False

    def _region(self, first, last, left, right):
        indices = (first, last, left, right)
        if (self.closed or any(type(x) is not int for x in indices)
                or not 0 <= first < last <= self.rows
                or not 0 <= left < right <= self.columns):
            raise ValueError('Open file and nonempty in-range integer region required')
        if 8*(last-first)*(right-left) > self.buffer_limit_bytes:
            raise ValueError('Region exceeds declared bounded panel capacity')

    def read(self, first, last, left, right):
        self._region(first, last, left, right)
        result = np.empty((last-first, right-left), dtype='float64', order='F')
        self.ledger.add('file.read.'+self.path.name, result)
        for j in range(left, right):
            self.stream.seek(8*(j*self.rows+first))
            buf = memoryview(result[:, j-left]).cast('B')
            count = self.stream.readinto(buf)
            if count != len(buf):
                raise OSError(('Short file panel read', self.path, count, len(buf)))
            self.read_bytes += count
            self.read_calls += 1
        self.max_read_buffer_bytes = max(self.max_read_buffer_bytes, result.nbytes)
        return result

    def write(self, first, last, left, right, value):
        self._region(first, last, left, right)
        value = np.asarray(value)
        if (value.shape != (last-first, right-left) or value.dtype != np.dtype('float64')
                or not np.isfinite(value).all()):
            raise ValueError('Finite FP64 panel with matching shape required')
        self.ledger.add('file.write.input_panel.'+self.path.name, value)
        self.max_write_panel_bytes = max(self.max_write_panel_bytes, value.nbytes)
        for j in range(left, right):
            column = np.ascontiguousarray(value[:, j-left])
            if not np.shares_memory(column, value):
                self.ledger.add('file.write.column_copy.'+self.path.name, column)
            self.stream.seek(8*(j*self.rows+first))
            buf = memoryview(column).cast('B')
            count = self.stream.write(buf)
            if count != len(buf):
                raise OSError(('Short file panel write', self.path, count, len(buf)))
            self.write_bytes += count
            self.write_calls += 1

    @classmethod
    def from_array(cls, path, value, block, ledger):
        """Small known controls only; a full producer must stream its columns."""
        value = np.asarray(value)
        if (value.ndim != 2 or value.dtype != np.dtype('float64')
                or max(value.shape) > 512):
            raise ValueError('FP64 small-known source matrix, at most512 per axis, required')
        result = cls(path, value.shape, block, ledger)
        try:
            for j in range(0, result.columns, block):
                stop = min(j+block, result.columns)
                result.write(0, result.rows, j, stop, value[:, j:stop])
        except BaseException:
            result.close()
            raise
        return result

    def audit_array(self):
        """Explicit small-only audit export, not used by production factor calls."""
        if max(self.shape) > 512:
            raise ValueError('Whole-matrix audit export is limited to known small shapes')
        result = np.empty(self.shape, order='F')
        self.ledger.add('audit_only.full_file_export.'+self.path.name, result)
        for j in range(0, self.columns, self.block):
            stop = min(j+self.block, self.columns)
            result[:, j:stop] = self.read(0, self.rows, j, stop)
        return result

    def report(self, digest=False):
        if not self.closed:
            self.stream.flush()
        result = dict(path=str(self.path), shape=list(self.shape), dtype='float64', order='F',
            file_bytes=self.path.stat().st_size, declared_bytes=self.size_bytes,
            block=self.block, panel_capacity_bytes=self.buffer_limit_bytes,
            max_read_buffer_bytes=self.max_read_buffer_bytes,
            max_write_panel_bytes=self.max_write_panel_bytes,
            read_bytes=self.read_bytes, write_bytes=self.write_bytes,
            read_calls=self.read_calls, write_calls=self.write_calls,
            mapped=False, closed=self.closed)
        if digest:
            with self.path.open('rb') as stream:
                result['sha256'] = hashlib.file_digest(stream, 'sha256').hexdigest()
        return result

    def close(self):
        if not self.closed:
            self.stream.close()
            self.closed = True

"""Direct GEQRF without a second rectangular R allocation.

Only the graph's square triangular factor is explicitly copied. Raw GEQRF
contains reflector entries below its diagonal; they are never treated as R.
"""
import numpy as np
from scipy import linalg


class Householder:
    def __init__(self, matrix, ledger, name):
        if matrix.dtype != np.dtype('float64') or not matrix.flags.f_contiguous:
            raise ValueError('Owned FP64 Fortran matrix required')
        self.rows, self.columns = matrix.shape
        self.k = min(matrix.shape)
        self.ledger, self.name = ledger, name
        geqrf = linalg.get_lapack_funcs('geqrf', (matrix,))
        # The -1 query returns a tiny work array, not the requested workspace.
        _, _, query, flag = geqrf(matrix, lwork=-1, overwrite_a=True)
        if flag:
            raise ArithmeticError(('geqrf workspace query', flag))
        self.lwork = int(query[0])
        raw, self.tau, work, flag = geqrf(matrix, lwork=self.lwork, overwrite_a=True)
        if flag:
            raise ArithmeticError(('geqrf', flag))
        self.raw = raw
        self.reflectors = raw[:, :self.k]
        self.alias = dict(input_and_raw_share=bool(np.shares_memory(matrix, raw)),
                          rectangular_R_allocated=False,
                          input_owns_data=bool(matrix.flags.owndata))
        for suffix, value in (('raw', raw), ('reflectors', self.reflectors),
                              ('tau', self.tau), ('geqrf_work', work)):
            ledger.add(name+'.'+suffix, value)
        ledger.snapshot(name+'.factored_with_work')
        self.ormqr = linalg.get_lapack_funcs('ormqr', (self.reflectors,))

    def graph_into(self, destination, block):
        """Fill [I; -R.T] in existing storage using bounded column buffers."""
        if destination.shape != (self.k+self.columns, self.k) or block < 1:
            raise ValueError('Graph dimensions/block differ')
        destination[:self.k] = 0
        np.fill_diagonal(destination[:self.k], 1.)
        for first in range(0, self.columns, block):
            last = min(first+block, self.columns)
            # Copy at most k*block values, never a full rectangular triu.
            buf = np.array(self.raw[:self.k, first:last].T, order='C', copy=True)
            self.ledger.add(self.name+'.graph_block.'+str(first), buf)
            for j in range(first, min(last, self.k)):
                buf[j-first, j+1:] = 0.
            np.negative(buf, out=buf)
            destination[self.k+first:self.k+last] = buf
        self.ledger.snapshot(self.name+'.graph_filled')

    def square_triangular(self):
        """Explicit F-contiguous T: avoids hidden strided-view TRTRS copies."""
        if self.k != self.columns:
            raise ValueError('Only a tall/square graph has a square factor')
        result = np.zeros((self.k, self.k), order='F')
        for j in range(self.k):
            result[:j+1, j] = self.raw[:j+1, j]
        self.ledger.add(self.name+'.square_R', result)
        self.ledger.snapshot(self.name+'.square_R_copied')
        return result

    def apply(self, value, transpose=False):
        value = np.asarray(value, float)
        vector = value.ndim == 1
        if value.ndim not in (1, 2) or value.shape[0] != self.rows:
            raise ValueError('Householder target dimensions differ')
        rhs = np.array(value[:, None] if vector else value, order='F', copy=True)
        self.ledger.add(self.name+'.ormqr_rhs', rhs)
        op = 'T' if transpose else 'N'
        _, query, flag = self.ormqr('L', op, self.reflectors, self.tau, rhs, lwork=-1)
        if flag:
            raise ArithmeticError(('ormqr workspace', flag))
        result, work, flag = self.ormqr('L', op, self.reflectors, self.tau, rhs,
                                       lwork=int(query[0]), overwrite_c=True)
        if flag:
            raise ArithmeticError(('ormqr', flag))
        self.ledger.add(self.name+'.ormqr_result', result)
        self.ledger.add(self.name+'.ormqr_work', work)
        self.ledger.snapshot(self.name+'.applied_'+op)
        return result[:, 0] if vector else result

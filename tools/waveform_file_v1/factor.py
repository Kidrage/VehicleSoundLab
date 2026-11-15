"""Blocked Householder QR, complete factors in explicit file storage."""
import numpy as np
from scipy import linalg
from .store import FileMatrix


class FileQR:
    def __init__(self, matrix):
        if not isinstance(matrix, FileMatrix) or matrix.closed:
            raise ValueError('Open explicitly owned file matrix required')
        self.raw = matrix
        self.rows, self.columns = matrix.shape
        self.k, self.block = min(matrix.shape), matrix.block
        self.ledger = matrix.ledger
        self.tau = np.empty(self.k)
        self.ledger.add('fileQR.tau.'+matrix.path.name, self.tau)
        self.calls = []
        for first in range(0, self.k, self.block):
            last = min(first+self.block, self.k)
            panel = matrix.read(first, self.rows, first, last)
            self._owned(panel)
            geqrf = linalg.get_lapack_funcs('geqrf', (panel,))
            _, _, query, flag = geqrf(panel, lwork=-1, overwrite_a=True)
            if flag:
                raise ArithmeticError(('panel geqrf workspace', flag))
            work_size = int(query[0])
            raw, tau, work, flag = geqrf(panel, lwork=work_size, overwrite_a=True)
            if flag or not np.shares_memory(raw, panel):
                raise ArithmeticError(('panel geqrf failed or copied', flag))
            self.ledger.add('fileQR.geqrf.raw', raw)
            self.ledger.add('fileQR.geqrf.work', work)
            self.ledger.add('fileQR.geqrf.tau', tau)
            self.calls.append(self._call('geqrf', panel, None, work_size, np.shares_memory(raw, panel)))
            self.tau[first:last] = tau
            matrix.write(first, self.rows, first, last, raw)
            self.ledger.snapshot('fileQR.panel.factored')
            for left in range(last, self.columns, self.block):
                right = min(left+self.block, self.columns)
                target = matrix.read(first, self.rows, left, right)
                updated = self._apply_panel(raw, tau, target, True)
                matrix.write(first, self.rows, left, right, updated)
                del target, updated
            del panel, raw, tau, work
        self.ledger.snapshot('fileQR.factor.complete')

    @staticmethod
    def _owned(value):
        if (not isinstance(value, np.ndarray) or isinstance(value, np.memmap)
                or value.dtype != np.dtype('float64') or value.ndim != 2
                or not value.flags.f_contiguous or not value.flags.owndata
                or not np.isfinite(value).all()):
            raise ValueError('Native kernels require finite owned FP64 Fortran panels')

    def _call(self, name, panel, rhs, work, aliases):
        return dict(kernel=name, panel_shape=list(panel.shape), panel_bytes=panel.nbytes,
            panel_owned=bool(panel.flags.owndata), panel_Fortran=bool(panel.flags.f_contiguous),
            target_shape=None if rhs is None else list(rhs.shape),
            target_bytes=0 if rhs is None else rhs.nbytes,
            target_owned=None if rhs is None else bool(rhs.flags.owndata),
            target_Fortran=None if rhs is None else bool(rhs.flags.f_contiguous),
            lwork=work, output_aliases_input=bool(aliases), whole_mapped_matrix=False)

    def _apply_panel(self, panel, tau, target, transpose):
        self._owned(panel)
        self._owned(target)
        ormqr = linalg.get_lapack_funcs('ormqr', (panel, target))
        op = 'T' if transpose else 'N'
        _, query, flag = ormqr('L', op, panel, tau, target, lwork=-1)
        if flag:
            raise ArithmeticError(('panel ormqr workspace', flag))
        size = int(query[0])
        result, work, flag = ormqr('L', op, panel, tau, target, lwork=size, overwrite_c=True)
        if flag or not np.shares_memory(result, target):
            raise ArithmeticError(('panel ormqr failed or copied', flag))
        self.ledger.add('fileQR.ormqr.result', result)
        self.ledger.add('fileQR.ormqr.work', work)
        self.calls.append(self._call('ormqr_'+op, panel, target, size, np.shares_memory(result, target)))
        self.ledger.snapshot('fileQR.panel.applied_'+op)
        return result

    def apply(self, value, transpose=False):
        value = np.asarray(value, dtype='float64')
        vector = value.ndim == 1
        if (value.ndim not in (1, 2) or value.shape[0] != self.rows
                or not np.isfinite(value).all()):
            raise ValueError('Finite Q target with matching full row dimension required')
        result = np.array(value[:, None] if vector else value, order='F', copy=True)
        self.ledger.add('fileQR.Q.complete_rhs', result)
        starts = list(range(0, self.k, self.block))
        for first in (starts if transpose else reversed(starts)):
            last = min(first+self.block, self.k)
            panel = self.raw.read(first, self.rows, first, last)
            for left in range(0, result.shape[1], self.block):
                right = min(left+self.block, result.shape[1])
                target = np.array(result[first:, left:right], order='F', copy=True)
                self.ledger.add('fileQR.Q.target_panel', target)
                result[first:, left:right] = self._apply_panel(panel, self.tau[first:last], target, transpose)
                del target
            del panel
        return result[:, 0] if vector else result

    def _upper_transpose_columns(self, first, last):
        panel = self.raw.read(first, last, 0, self.columns)
        for j in range(first, last):
            panel[j-first, :j] = 0.
        result = np.array(panel.T, order='F', copy=True)
        self.ledger.add('fileQR.transpose.upper_panel', result)
        self.ledger.snapshot('fileQR.upper_transpose.materialized')
        return result

    def transpose_R(self, path):
        result = FileMatrix(path, (self.columns, self.k), self.block, self.ledger)
        for first in range(0, self.k, self.block):
            last = min(first+self.block, self.k)
            panel = self._upper_transpose_columns(first, last)
            result.write(0, self.columns, first, last, panel)
        return result

    def graph(self, path):
        result = FileMatrix(path, (self.k+self.columns, self.k), self.block, self.ledger)
        for first in range(0, self.k, self.block):
            last = min(first+self.block, self.k)
            top = np.zeros((self.k, last-first), order='F')
            self.ledger.add('fileQR.graph.identity_panel', top)
            top[np.arange(first, last), np.arange(last-first)] = 1.
            result.write(0, self.k, first, last, top)
            panel = self._upper_transpose_columns(first, last)
            np.negative(panel, out=panel)
            result.write(self.k, self.k+self.columns, first, last, panel)
        return result

    def report(self):
        return dict(rows=self.rows, columns=self.columns, retained_directions=self.k,
            block=self.block, native_calls=self.calls, full_R_and_reflectors_on_disk=True,
            explicit_full_Q=False, file=self.raw.report(digest=True))

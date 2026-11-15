"""Experimental leading-dimension access to QR's upper triangle, no T copy.

Not selected by NormalInverse. The declared SciPy Cython LAPACK ABI must match;
the native-shape audit proves this host only, not an arbitrary target build.
"""
import ctypes
import numpy as np
from scipy.linalg import cython_lapack


class NativeUpperTriangular:
    def __init__(self, raw, size):
        if not isinstance(raw, np.ndarray) or raw.dtype != np.dtype('float64'):
            raise ValueError('Existing FP64 ndarray required; no conversion allowed')
        if raw.ndim != 2 or not raw.flags.f_contiguous or min(raw.shape) < size or size < 1:
            raise ValueError('Complete Fortran QR storage and positive triangle required')
        if raw.strides != (8, 8*raw.shape[0]) or max(raw.shape) > 2**31-1:
            raise ValueError('Only declared LP64 contiguous leading dimension supported')
        for j in range(size):
            if not np.isfinite(raw[:j+1, j]).all():
                raise ValueError('Nonfinite upper triangle')
        self.raw, self.size = raw, int(size)
        capsule = cython_lapack.__pyx_capi__['dtrtrs']
        name = ctypes.pythonapi.PyCapsule_GetName
        name.argtypes, name.restype = [ctypes.py_object], ctypes.c_char_p
        signature = name(capsule)
        if (not signature.startswith(b'void (char *, char *, char *, int *, int *, ')
                or not signature.endswith(b' *, int *, int *)')
                or signature.count(b'int *') != 5):
            raise RuntimeError('Unqualified SciPy dtrtrs Cython ABI: '+repr(signature))
        pointer = ctypes.pythonapi.PyCapsule_GetPointer
        pointer.argtypes, pointer.restype = [ctypes.py_object, ctypes.c_char_p], ctypes.c_void_p
        pc, pi, pd = (ctypes.POINTER(t) for t in (ctypes.c_char, ctypes.c_int, ctypes.c_double))
        self.function = ctypes.CFUNCTYPE(None, pc, pc, pc, pi, pi, pd, pi, pd, pi, pi)(pointer(capsule, signature))
        self.signature = signature.decode('ascii')

    def solve_inplace(self, rhs, transpose=False):
        if (not isinstance(rhs, np.ndarray) or rhs.dtype != np.dtype('float64')
                or rhs.ndim != 2 or rhs.shape[0] != self.size or rhs.shape[1] < 1
                or rhs.shape[1] > 2**31-1 or not rhs.flags.f_contiguous
                or not rhs.flags.writeable or not np.isfinite(rhs).all()
                or np.shares_memory(rhs, self.raw)):
            raise ValueError('Independent writable complete FP64 Fortran RHS required')
        upper, trans, diagonal = (ctypes.c_char(v) for v in (b'U', b'T' if transpose else b'N', b'N'))
        n, nrhs, lda, ldb, info = (ctypes.c_int(v) for v in
                                  (self.size, rhs.shape[1], self.raw.shape[0], self.size, 0))
        pd = ctypes.POINTER(ctypes.c_double)
        self.function(ctypes.byref(upper), ctypes.byref(trans), ctypes.byref(diagonal),
                      ctypes.byref(n), ctypes.byref(nrhs), self.raw.ctypes.data_as(pd),
                      ctypes.byref(lda), rhs.ctypes.data_as(pd), ctypes.byref(ldb), ctypes.byref(info))
        if info.value:
            raise ArithmeticError(('native dtrtrs', info.value))
        return rhs

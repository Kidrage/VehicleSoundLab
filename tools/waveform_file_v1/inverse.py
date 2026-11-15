"""Complete inverse-normal action from file QR, retaining identity complement."""
import numpy as np
from .factor import FileQR
from .triangle import solve


class FileNormalInverse:
    def __init__(self, source):
        if not isinstance(source, FileQR):
            raise ValueError('Complete source file QR required')
        self.size, self.k = source.columns, source.k
        parent = source.raw.path.parent
        self.right = FileQR(source.transpose_R(parent/'right.bin'))
        self.inner = FileQR(self.right.graph(parent/'inner.bin'))

    def apply(self, value):
        value = np.asarray(value, dtype='float64')
        if (value.ndim not in (1, 2) or value.shape[0] != self.size
                or not np.isfinite(value).all()):
            raise ValueError('Finite complete source RHS required')
        coordinates = self.right.apply(value, True)
        coordinates[:self.k] = solve(self.inner, solve(self.inner, coordinates[:self.k], True))
        return self.right.apply(coordinates)

    def audit_arrays(self):
        return dict(inverse_right_raw=self.right.raw.audit_array(), inverse_right_tau=self.right.tau,
            inverse_inner_raw=self.inner.raw.audit_array(), inverse_inner_tau=self.inner.tau)

    def info(self):
        return dict(method='bounded_file_QR_complete_inverse', source_columns=self.size,
            retained_inner_directions=self.k, identity_complement_directions=self.size-self.k,
            separate_square_T_allocated=False, explicit_full_Q=False,
            normal_equation_factorization=False, subtractive_Woodbury=False,
            right=self.right.report(), inner=self.inner.report(),
            full_or_real_resource_qualification=False)

    def close(self):
        self.right.raw.close()
        self.inner.raw.close()

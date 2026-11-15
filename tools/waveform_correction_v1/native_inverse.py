"""Opt-in original inverse action using the existing QR triangle, no T copy."""
from .inverse import NormalInverse


class NativeNormalInverse(NormalInverse):
    native_triangle=True

    def info(self):
        result=super().info()
        result.update(native_triangle_ABI=self.native_T.signature,
                      native_triangle_leading_dimension=self.native_T.raw.shape[0],
                      native_triangle_aliases_inner_raw=self.native_T.raw is self.inner.raw)
        return result

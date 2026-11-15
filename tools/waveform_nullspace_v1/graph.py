"""Declared triangular evaluation of the same untruncated graph projection."""
from .algebra import solve as nullspace_solve


def solve(Phi,W,R,target):
    return nullspace_solve(Phi,W,R,target,triangular_top=True)

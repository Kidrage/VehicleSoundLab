"""Exact first circular moments of the two DIFFERENT interpolation laws."""
import numpy as np
from .surface import row_inverse


def conditional_mixture(weight, left, right, low, high):
    cell=np.exp(.5j*(low+high))*np.sinc((high-low)/(2*np.pi))
    a=np.diff(left)@cell;b=np.diff(right)@cell
    return (1-np.asarray(weight))*a+np.asarray(weight)*b


def quantile_blend(weight, left, right, low, high):
    # Each row inverse is affine on intervals cut by BOTH rows' CDF nodes.
    # Integrate exp(i * affine(u)) exactly, including constant atom intervals.
    edges=np.unique(np.r_[left,right]);width=np.diff(edges)
    a=row_inverse(edges,left,low,high);b=row_inverse(edges,right,low,high)
    w=np.asarray(weight)[...,None]
    start=(1-w)*a[:-1]+w*b[:-1];end=(1-w)*a[1:]+w*b[1:]
    return np.sum(width*np.exp(.5j*(start+end))*np.sinc((end-start)/(2*np.pi)),axis=-1)

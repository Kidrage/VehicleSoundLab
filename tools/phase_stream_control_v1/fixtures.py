"""Deterministic known quantiles; no recorded source or random generator."""
import numpy as np


def cases():
    return {
        'one_atom': np.array([[.7, -.9]]),
        'two_atoms_and_bridge': np.array([[-2., 1.], [3., 7.]]),
        'repeated_values': np.array([[-2., 0.], [-2., 0.], [1., 0.], [1., 4.], [3., 4.]]),
        'unwrapped_phase': np.array([[-7., -6.], [-3.13, -3.], [3.13, 2.], [8., 10.]]),
        'unequal_slopes': np.array([[-20., -3.], [-.001, -2.999], [0., .1], [.0001, 14.], [40., 15.]]),
        '39_rows': np.column_stack([np.linspace(-2, 3, 39)**3, np.linspace(-4, 7, 39)]),
        '40_rows': np.column_stack([np.linspace(-3, 2, 40), np.linspace(-2, 3, 40)**3]),
        '41_rows': np.column_stack([np.linspace(-4, 2, 41), np.linspace(-1, 2, 41)**3]),
    }


def uniforms(count):
    nodes = np.r_[0., (np.arange(count)+.5)/count, 1.]
    return np.unique(np.clip(np.r_[nodes, np.nextafter(nodes, 0.),
        np.nextafter(nodes, 1.), np.linspace(0, 1, 257)], 0, 1))

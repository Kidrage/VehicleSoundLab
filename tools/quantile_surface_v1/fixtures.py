"""Declared small conditional rows; no material access or random generator."""
import numpy as np


def cases():
    cells = dict(low=np.array([-1., -1., 1.]), high=np.array([-1., 1., 1.]))
    yield dict(name='identical_rows', knots=np.array([0., 1.]),
               cdf=np.array([[0., .2, .8, 1.], [0., .2, .8, 1.]]), **cells)
    yield dict(name='single_node', knots=np.array([1.]),
               cdf=np.array([[0., .2, .8, 1.]]), **cells)
    yield dict(name='moving_atom_mass', knots=np.array([0., 1.]),
               cdf=np.array([[0., .9999, .99995, 1.], [0., .00005, .0001, 1.]]), **cells)
    yield dict(name='three_unequal_knots', knots=np.array([0., .125, 2.]),
               cdf=np.array([[0., .1, .7, 1.], [0., .6, .8, 1.], [0., .15, .95, 1.]]), **cells)
    yield dict(name='constant_phase_atom', knots=np.array([0., 1.]),
               cdf=np.array([[0., .4, 1.], [0., .8, 1.]]),
               low=np.array([2., 2.]), high=np.array([2., 2.]))
    yield dict(name='repeated_phase_atoms', knots=np.array([0., 1.]),
               cdf=np.array([[0., .1, .3, .8, 1.], [0., .2, .25, .6, 1.]]),
               low=np.array([1., 1., 1., 3.]), high=np.array([1., 1., 3., 3.]))
    yield dict(name='extended_phase_branch', knots=np.array([0., 1.]),
               cdf=np.array([[0., .2, .6, 1.], [0., .1, .9, 1.]]),
               low=np.array([6., 6., 10.]), high=np.array([6., 10., 10.]))

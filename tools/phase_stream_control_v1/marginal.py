"""Represent the original continuous empirical inverse, including its atoms."""
import numpy as np


def cells(column, knots):
    column = np.asarray(column)
    count = len(column)
    assert count and np.all(np.diff(column) >= 0)
    lower = np.r_[column[0], column[:-1], column[-1]]
    upper = np.r_[column[0], column[1:], column[-1]]
    probability = np.r_[0., (np.arange(count)+.5)/count, 1.]
    return np.broadcast_to(probability, (len(knots), len(probability))).copy(), lower, upper

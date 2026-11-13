"""Original relative-envelope cone and exact fixed-angle coefficient caps."""
import numpy as np
import scipy.sparse as sp


def ranged(shape, bound, caps):
    parts, controls = shape
    rows, columns, entries = [], [], []
    low, high = [], []
    for part in range(parts):
        first = part*controls
        row = len(low)
        rows.append(row); columns.append(first); entries.append(1.)
        low.append(0.); high.append(float(caps[part]))
        for control in range(1, controls):
            row = len(low)
            rows.extend((row, row)); columns.extend((first, first+control)); entries.extend((1-bound, -1.))
            low.append(-np.inf); high.append(0.)
            row = len(low)
            rows.extend((row, row)); columns.extend((first, first+control)); entries.extend((-(1+bound), 1.))
            low.append(-np.inf); high.append(0.)
    matrix = sp.csc_matrix((entries, (rows, columns)), shape=(len(low), parts*controls))
    return matrix, np.asarray(low), np.asarray(high)

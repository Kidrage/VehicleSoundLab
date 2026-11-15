"""Waveform-root interface; dense implementation preserves the frozen actions."""
import numpy as np
from scipy import linalg


class DenseRoot:
    kind='dense_cholesky'
    def __init__(self,metric,ledger):
        ledger.add('wave_metric.input',metric);ledger.snapshot('metric.before_root')
        self.L=linalg.cholesky(metric,lower=True,overwrite_a=True,check_finite=False)
        self.shares_input=bool(np.shares_memory(self.L,metric))
        ledger.add('wave_metric.L',self.L)
    def apply(self,x):return self.L@x
    def transpose(self,x):return self.L.T@x
    def solve_transpose(self,x):
        return linalg.solve_triangular(self.L,x,trans='T',lower=True,check_finite=False)


def factor(metric,ledger):
    return metric.factor(ledger) if callable(getattr(metric,'factor',None)) else DenseRoot(metric,ledger)

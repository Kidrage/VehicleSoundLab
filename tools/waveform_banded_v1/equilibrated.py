"""Experimental invertible diagonal equilibration of the SAME band metric.

Not selected by the production metric factory. After native factorization,
restore row scales so inherited actions still use a root of the original W.
"""
import numpy as np
from .root import BandedRoot


class EquilibratedRoot(BandedRoot):
    kind='experimental_equilibrated_lower_band_cholesky'

    def __init__(self,bands,ledger):
        scales=np.sqrt(bands[0].copy())
        if not np.isfinite(scales).all() or np.any(scales<=0):
            raise ValueError('Positive finite metric diagonal required')
        inverse=1/scales
        ledger.add('metric.equilibration_scales',scales)
        ledger.add('metric.equilibration_inverse',inverse)
        size,frames=bands.shape
        for d in range(size):
            bands[d,:frames-d]*=inverse[d:]
            bands[d,:frames-d]*=inverse[:frames-d]
        super().__init__(bands,ledger)
        for d in range(size):self.L[d,:frames-d]*=scales[d:]
        ledger.snapshot('metric.equilibrated_scales_restored')

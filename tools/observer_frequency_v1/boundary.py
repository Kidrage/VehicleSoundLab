"""Separate partial boundary frames from fully supported spectral observations."""
import numpy as np
from .metric import FrequencyMetric

EDGES=(0.,3000.,6000.,8000.,10000.,14000.,21600.,np.inf)


def analyze(audio,root,candidates):
    metric=FrequencyMetric(audio,root);frame=metric.frame
    rows=frame.forward(audio);freq=np.arange(2049)*root/4
    masks=np.array([(freq>=a)&(freq<b) for a,b in zip(EDGES[:-1],EDGES[1:])])
    # Source records here exceed a full frame: left and right cannot overlap.
    left=frame.starts<0;right=frame.starts+4096>len(audio)
    if np.any(left&right):raise ValueError('This partition requires record >=4096')
    parts=(left,~(left|right),right)
    def energies(z,weighted=False):
        if weighted:z=z*metric.weights[None,:,None]
        return np.array([[np.sum(abs(z[part][:,band])**2,axis=(0,1)) for band in masks] for part in parts])
    reference=energies(rows);joint=reference.sum(axis=(0,2))
    results=dict(reference_energy=reference,part_rows=np.array([p.sum() for p in parts]),
        reference_endcap_fraction=np.divide(reference[[0,2]].sum(axis=(0,2)),joint,out=np.zeros_like(joint),where=joint>0),
        metric_band_power=metric.band_power,metric_floor=metric.global_power*metric.floor_fraction,
        metric_floor_active=metric.band_power<metric.global_power*metric.floor_fraction)
    for tag,wave in candidates.items():
        residual=frame.forward(wave)-rows
        results[tag+'_weighted_residual_energy']=energies(residual,True)
        results[tag+'_residual_energy']=energies(residual)
    return results

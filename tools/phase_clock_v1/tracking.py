"""Prefer a complete FFT family; try a complete chirplet family on failure."""
from shift_evidence_v1.spectrum import observe
from state_colour_v2.clock import follow
from .chirplet import observe as chirplet_observe


def track(audio,source_start,start,stop,anchor,reference=5):
    evidence=[]
    for method in ('fft','chirplet'):
        s=observe(audio,source_start,80,hop=240) if method=='fft' else chirplet_observe(audio,source_start)
        path=follow(s['hz'],s['seconds'],s['power_low'],start,stop,anchor,reference)
        evidence.append(dict(method=method,status=path['status']))
        if path['rows']:return path,dict(selected=method,attempts=evidence)
    return path,dict(selected=None,attempts=evidence)

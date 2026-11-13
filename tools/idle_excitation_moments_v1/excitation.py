"""Fresh statistical excitation; no clip, phase-clock, driving or spatial code."""
import math
import numpy as np
from sustain_osc_v1.oracle import Gaussian

MASK=(1<<64)-1


def streams(seed,index,count,probability):
    key=seed^(0x9E3779B97F4A7C15*(index+1)&MASK)
    old=Gaussian(key);marks=Gaussian(key^0xD1B54A32D192ED03)
    amplitude=Gaussian(key^0x94D049BB133111EB)
    gaussian=np.fromiter((old.next() for _ in range(count)),float,count=count)
    sparse=np.empty(count);events=0
    for j in range(count):
        # Both RNGs advance on every frame, including silent marks.
        on=marks.uniform()/2**53<probability;z=amplitude.next()
        sparse[j]=z/math.sqrt(probability) if on else 0.
        events+=int(on)
    return gaussian,sparse,events


def blend(gaussian,sparse,amount):
    if not np.isfinite(amount) or not 0<=amount<=1: raise ValueError('Expected0..1 amount')
    if amount==0:return gaussian.copy()
    return math.sqrt(1-amount)*gaussian+math.sqrt(amount)*sparse

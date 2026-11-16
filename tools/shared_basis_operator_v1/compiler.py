"""Shared rounded column blocks, generated identically for both directions."""
from collections import OrderedDict
import numpy as np


class Compiler:
    def __init__(self,geometry,*,cache_bytes=64*1024**2,column_batch=32):
        if type(cache_bytes) is not int or cache_bytes<0 or type(column_batch) is not int or not 1<=column_batch<=128:
            raise ValueError('Explicit bounded block cache and column batch required')
        self.g=geometry;self.limit=cache_bytes;self.batch=column_batch;self.cache=OrderedDict();self.cached_bytes=0
        self.compiled_blocks=0;self.cache_hits=0

    def wave(self,first,last):
        ids=self.g.active(first,last);matrix=self.g.columns(first,last,ids)
        return ids,matrix

    def spectral(self,index):
        if index in self.cache:
            value=self.cache.pop(index);self.cache[index]=value;self.cache_hits+=1;return value
        g=self.g;first=int(g.starts[index]);ids=g.active(first,first+4096)
        matrix=np.empty((4098,len(ids)))
        for offset in range(0,len(ids),self.batch):
            subset=ids[offset:offset+self.batch];samples=g.columns(first,first+4096,subset)
            samples*=g.normalizer[first:first+4096,None];samples*=g.window[:,None]
            for j in range(len(subset)):
                # Each finite-basis column has one canonical declared FFT.
                # After compilation, both actions multiply these SAME values.
                row=np.fft.rfft(samples[:,j])*g.endpoint/64
                row*=g.amplitude;row*=g.weights
                matrix[:2049,offset+j]=row.real;matrix[2049:,offset+j]=row.imag
        ids.flags.writeable=False;matrix.flags.writeable=False;value=(ids,matrix);self.compiled_blocks+=1
        cost=ids.nbytes+matrix.nbytes
        if cost<=self.limit:
            while self.cache and self.cached_bytes+cost>self.limit:
                _,old=self.cache.popitem(last=False);self.cached_bytes-=old[0].nbytes+old[1].nbytes
            self.cache[index]=value;self.cached_bytes+=cost
        return value

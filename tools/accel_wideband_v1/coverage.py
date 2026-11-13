"""Native band power identity keeps interference; residual is not a noise source."""
import numpy as np


def oscillator_model(row,frames=12000,rate=48000,eligible=False):
    t=(np.arange(frames)-frames/2)/rate
    output=np.tile(row['DC_LR'],(frames,1)).astype(float)
    for line in row['lines']:
        if eligible and not line['eligible']:continue
        angle=2*np.pi*(line['frequency_hz']*t+.5*line['chirp_hz_per_second']*t*t)
        output+=np.cos(angle)[:,None]*line['cosine_LR']+np.sin(angle)[:,None]*line['sine_LR']
    return output


def decomposition(source,model,bands,rate=48000):
    n=len(source);window=.5-.5*np.cos(2*np.pi*np.arange(n)/n)
    X=np.fft.rfft(source*window[:,None],axis=0);Y=np.fft.rfft(model*window[:,None],axis=0)
    R=X-Y;factor=np.full(len(X),2.);factor[[0,-1]]=1
    factor=factor[:,None]/(n*np.sum(window*window));hz=np.fft.rfftfreq(n,1/rate)
    arrays=dict(source=abs(X)**2*factor,model=abs(Y)**2*factor,residual=abs(R)**2*factor,
        interference=2*(Y*R.conj()).real*factor)
    result={key:np.array([value[(hz>=lo)&(hz<hi)].sum(axis=0) for lo,hi in bands]) for key,value in arrays.items()}
    error=float(abs(result['source']-result['model']-result['residual']-result['interference']).max())
    return {key:value.tolist() for key,value in result.items()},error

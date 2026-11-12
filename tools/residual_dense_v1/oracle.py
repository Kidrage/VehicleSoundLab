"""Direct trigonometric sum, independently reconstructing constant-pitch C clouds."""
import math
import numpy as np


def read(path):
    lines=path.read_text(encoding='ascii').splitlines()
    header=lines[0].split();assert header[:3]==['VSL_SOUND_RESIDUAL','1','48000']
    rows=np.array([[float(v) for v in line.split()] for line in lines[1:]])
    assert rows.shape==(int(header[3]),6)
    return rows


def counts(rows,peak):
    return np.array([max(32,min(256,math.ceil((r[1]-r[0])*peak/2000))) for r in rows],dtype=int)


def render(rows,partials,seed,frames,pitch=1):
    def uniform():
        nonlocal seed
        mask=(1<<64)-1;seed=(seed+0x9e3779b97f4a7c15)&mask
        z=seed;z=((z^(z>>30))*0xbf58476d1ce4e5b9)&mask
        z=((z^(z>>27))*0x94d049bb133111eb)&mask
        return ((z^(z>>31))>>11)/2**53
    frequency=[];phase=[];left=[];right_re=[];right_im=[]
    for row,n in zip(rows,partials):
        low,high,pl,pr,re,im=row;step=(high-low)/int(n)
        al=math.sqrt(2*pl/int(n));ar=math.sqrt(2*pr/int(n))
        independent=ar*math.sqrt(max(0,1-re*re-im*im))
        for j in range(int(n)):
            f=low+(j+.15+.25*uniform())*step
            other=low+(j+.65+.25*uniform())*step
            a=2*math.pi*uniform();b=2*math.pi*uniform()
            frequency.extend((f,other));phase.extend((a,b))
            left.extend((al,0));right_re.extend((ar*re,independent));right_im.extend((ar*im,0))
    frequency=np.array(frequency);phase=np.array(phase)
    out=np.zeros((frames,2));t=np.arange(frames)/48000
    for start in range(0,frames,128):
        angle=2*np.pi*pitch*t[start:start+128,None]*frequency[None,:]+phase[None,:]
        cosine,sine=np.cos(angle),np.sin(angle)
        out[start:start+128,0]=cosine@np.array(left)
        out[start:start+128,1]=cosine@np.array(right_re)-sine@np.array(right_im)
    return out

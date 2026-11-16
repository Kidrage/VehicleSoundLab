"""Read, edit and validate the existing Sound DNA parameter contract."""
from pathlib import Path
import numpy as np
from sound_dna.profile import export


DEFAULTS = dict(pitch=1., detail=1., gain_db=-6., low_db=0., mid_db=0., high_db=0.,
                tilt=0., width=1., shared=1., local=1., seconds=4., seed=48271)
LIMITS = dict(pitch=(.9,1.1), detail=(0,1), gain_db=(-36,0), low_db=(-12,12),
              mid_db=(-12,12), high_db=(-12,12), tilt=(-3,3), width=(0,1.5),
              shared=(0,2), local=(0,2), seconds=(.25,12), seed=(1,2**32-1))


def read(path):
    lines = Path(path).read_text(encoding='ascii').splitlines()
    header = lines[0].split()
    if header[0] not in ('VSL_SOUND_DNA', 'VSL_SUSTAIN_OSC') or header[1:5] != ['1','48000','1024','256']:
        raise ValueError('不支持的DNA模型格式')
    h,k = map(int,header[5:7])
    base = float(header[7]) if header[0]=='VSL_SOUND_DNA' else 46.875
    data = np.asarray([[float(v) for v in line.split()] for line in lines[2:]])
    if not 1<=h<=320 or not 0<=k<=16 or data.shape!=(h,4+4*k+17):
        raise ValueError('模型维度不符合现有C接口')
    model = dict(mean=data[:,:4].copy(), basis=data[:,4:4+4*k].reshape(h,k,4).copy(),
                 rho=np.asarray([float(v) for v in lines[1].split()]),
                 residual_rho=data[:,4+4*k].copy(), root=data[:,-16:].reshape(h,4,4).copy())
    validate(model,base)
    return model,base


def validate(m,base):
    if set(m)!= {'mean','basis','rho','residual_rho','root'} or m['basis'].ndim!=3:
        raise ValueError('模型需要完整mean／basis／rho／residual_rho／root数组')
    h,k = m['basis'].shape[:2]
    if not 1<=h<=320 or not 0<=k<=16:
        raise ValueError('模型阶数需1–320，联动成分需0–16')
    shapes=dict(mean=(h,4),basis=(h,k,4),rho=(k,),residual_rho=(h,),root=(h,4,4))
    if not 5<=base<=2000 or h*base*1.1>21600:
        raise ValueError('阶数／基频超过现有C声源的带宽范围')
    for name,shape in shapes.items():
        value=np.asarray(m[name])
        bound=.95 if name in ('rho','residual_rho') else 4.
        if value.shape!=shape or not np.isfinite(value).all() or np.any(abs(value)>bound):
            raise ValueError('参数超出C模型范围：'+name)


def describe(m,base):
    mean=m['mean'];h=len(mean)
    return dict(root_hz=base,harmonics=h,components=len(m['rho']),
        rows=[dict(order=i+1,hz=(i+1)*base,
                   left=float(np.hypot(*mean[i,:2])),right=float(np.hypot(*mean[i,2:])),
                   phase_l=float(np.degrees(np.arctan2(mean[i,1],mean[i,0]))),
                   phase_r=float(np.degrees(np.arctan2(mean[i,3],mean[i,2]))),
                   residual_rho=float(m['residual_rho'][i])) for i in range(h)],
        rho=m['rho'].tolist())


def controls(values):
    p=dict(DEFAULTS)
    if not isinstance(values,dict) or set(values)-set(p):
        raise ValueError('未知调音参数')
    p.update(values)
    for key,(lo,hi) in LIMITS.items():
        value=p[key]
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not np.isfinite(value) or not lo<=value<=hi:
            raise ValueError('参数范围错误：'+key)
    if int(p['seed'])!=p['seed']:
        raise ValueError('种子必须为整数')
    p['seed']=int(p['seed'])
    return p


def edit(original,base,p,rows=None,rho=None):
    m={k:v.copy() for k,v in original.items()}
    if rows is not None:
        if len(rows)!=len(m['mean']): raise ValueError('分音表行数不匹配')
        for i,row in enumerate(rows):
            for c,a,phase in ((0,'left','phase_l'),(2,'right','phase_r')):
                amp=float(row[a]);angle=float(row[phase])
                if not np.isfinite([amp,angle]).all() or not 0<=amp<=4 or abs(angle)>3600:
                    raise ValueError('分音幅相超出范围')
                m['mean'][i,c:c+2]=amp*np.array([np.cos(np.radians(angle)),np.sin(np.radians(angle))])
            m['residual_rho'][i]=float(row['residual_rho'])
    if rho is not None: m['rho']=np.asarray(rho,dtype=float)
    hz=np.arange(1,len(m['mean'])+1)*base
    band=np.where(hz<250,p['low_db'],np.where(hz<2500,p['mid_db'],p['high_db']))
    db=band+p['tilt']*np.log2(np.maximum(hz,20)/1000)+p['gain_db']
    scale=10**(db/20)
    m['mean']*=scale[:,None]
    m['basis']*=scale[:,None,None]*p['shared']
    m['root']*=scale[:,None,None]*p['local']
    # Parameter-space M/S transform; transforms covariance factors too.
    # No new room, delay, independent noise source or runtime DSP is added.
    w=p['width'];t=np.array([[1+w,0,1-w,0],[0,1+w,0,1-w],
                            [1-w,0,1+w,0],[0,1-w,0,1+w]])/2
    m['mean']=m['mean']@t.T
    m['basis']=m['basis']@t.T
    m['root']=t[None]@m['root']
    validate(m,base)
    return m


def write(path,m,base):
    validate(m,base)
    export(Path(path),m,base)

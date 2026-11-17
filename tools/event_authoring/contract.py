"""Standard-library contract shared by authoring and vehicle hosts."""
import math
import ctypes as ct

KINDS=('engage','crank','catch','afterfire','shift','disengage','stop')


def validate(p):
    def within(value,low,high):return not isinstance(value,bool) and isinstance(value,(int,float)) and math.isfinite(value) and low<=value<=high
    required={'gated','duration_seconds','attack_seconds','release_seconds','sweep_seconds','level','modes','bands'}
    if not isinstance(p,dict) or not required<=set(p) or set(p)-required-{'noise_lowpass_hz','contours'}:
        raise ValueError('Event profile fields do not match contract')
    if 'noise_lowpass_hz' in p and not (within(p['noise_lowpass_hz'],0,0) or within(p['noise_lowpass_hz'],300,18000)):
        raise ValueError('Invalid source-noise lowpass frequency')
    for key,low,high in [('duration_seconds',.005,30),('attack_seconds',0,2),('release_seconds',.001,2),
                         ('sweep_seconds',0,10),('level',0,8)]:
        if not within(p[key],low,high):raise ValueError('Invalid profile '+key)
    if type(p['gated']) is not int or p['gated'] not in (0,1) or not isinstance(p['modes'],list) or not isinstance(p['bands'],list) or len(p['modes'])>12 or len(p['bands'])>4:raise ValueError('Event capacity exceeded')
    for m in p['modes']:
        required_mode={'hz','end_hz','amplitude','phase','decay_seconds'}
        if not isinstance(m,dict) or not required_mode<=set(m) or set(m)-required_mode-{'attack_seconds'}:raise ValueError('Invalid mode fields')
        if 'attack_seconds' in m and not within(m['attack_seconds'],0,2):raise ValueError('Invalid mode attack_seconds')
        for key,low,high in [('hz',20,18000),('end_hz',20,18000),('amplitude',0,4),('phase',-48000,48000),('decay_seconds',.002,10)]:
            if not within(m[key],low,high):raise ValueError('Invalid mode '+key)
    for b in p['bands']:
        if not isinstance(b,dict) or set(b)!={'hz','q','amplitude','attack_seconds','decay_seconds'}:raise ValueError('Invalid band fields')
        for key,low,high in [('hz',30,16000),('q',.15,30),('amplitude',0,8),('attack_seconds',0,2),('decay_seconds',.002,10)]:
            if not within(b[key],low,high):raise ValueError('Invalid band '+key)
    curves=p.get('contours',[])
    if not isinstance(curves,list) or len(curves)>4:raise ValueError('At most four source contours')
    for i,c in enumerate(curves):
        if not isinstance(c,dict) or set(c)!={'low_hz','high_hz','seconds','gain'}:raise ValueError('Invalid contour fields')
        if not within(c['low_hz'],0,24000) or not within(c['high_hz'],0,24000) or c['low_hz']>=c['high_hz']:raise ValueError('Invalid contour range')
        if not isinstance(c['seconds'],list) or not isinstance(c['gain'],list) or not 2<=len(c['seconds'])<=8 or len(c['seconds'])!=len(c['gain']):raise ValueError('Contour requires 2–8 time/gain knots')
        if any(not within(v,0,30) for v in c['seconds']) or c['seconds'][0]!=0 or any(b<=a for a,b in zip(c['seconds'],c['seconds'][1:])):raise ValueError('Contour times must start at zero and increase')
        if any(not within(v,0,8) for v in c['gain']):raise ValueError('Invalid contour gain')
        if any(c['low_hz']<b['high_hz'] and b['low_hz']<c['high_hz'] for b in curves[:i]):raise ValueError('Contour ranges overlap')
    return p


class ModeV1(ct.Structure):
    _fields_=[(k,ct.c_double) for k in ('hz','amplitude','phase','decay_seconds','end_hz')]


class Mode(ct.Structure):
    _fields_=[*ModeV1._fields_,('attack_seconds',ct.c_double)]


class Band(ct.Structure):
    _fields_=[(k,ct.c_double) for k in ('hz','q','amplitude','attack_seconds','decay_seconds')]


class ProfileV1(ct.Structure):
    _fields_=[(k,ct.c_uint) for k in ('mode_count','band_count','gated')]+[
        (k,ct.c_double) for k in ('duration_seconds','attack_seconds','release_seconds','sweep_seconds','level')]+[
        ('modes',ModeV1*12),('bands',Band*4)]


class ProfileV2(ct.Structure):
    _fields_=[*ProfileV1._fields_,('noise_lowpass_hz',ct.c_double)]


class ProfileV3(ct.Structure):
    _fields_=[(k,ct.c_uint) for k in ('mode_count','band_count','gated')]+[
        (k,ct.c_double) for k in ('duration_seconds','attack_seconds','release_seconds','sweep_seconds','level')]+[
        ('modes',Mode*12),('bands',Band*4),('noise_lowpass_hz',ct.c_double)]


class Contour(ct.Structure):
    _fields_=[('count',ct.c_uint),('low_hz',ct.c_double),('high_hz',ct.c_double),
        ('seconds',ct.c_double*8),('gain',ct.c_double*8)]


class Profile(ct.Structure):
    _fields_=[*ProfileV3._fields_,('contours',Contour*4)]


class Request(ct.Structure):
    _fields_=[('id',ct.c_uint64),('requested_frame',ct.c_uint64),('type',ct.c_uint),
        ('priority',ct.c_uint),('seed',ct.c_uint32)]+[
        (k,ct.c_double) for k in ('strength','pitch','decay','texture')]


def pack_profile(profile,profile_class=Profile):
    validate(profile)
    native=profile_class();native.mode_count=len(profile['modes']);native.band_count=len(profile['bands'])
    if profile_class is ProfileV1 and profile.get('noise_lowpass_hz',0):
        raise ValueError('This event uses source-noise coloration; use event ABI2 / vehicle ABI6')
    if profile_class in (ProfileV1,ProfileV2) and any(m.get('attack_seconds',0) for m in profile['modes']):
        raise ValueError('Modal attacks require event ABI3 / vehicle ABI10')
    if profile_class is not Profile and profile.get('contours'):raise ValueError('Contours require event ABI4 / vehicle ABI11')
    if profile_class is not ProfileV1:native.noise_lowpass_hz=profile.get('noise_lowpass_hz',0.)
    for key in ('gated','duration_seconds','attack_seconds','release_seconds','sweep_seconds','level'):
        setattr(native,key,profile[key])
    for key,cls in (('modes',ModeV1 if profile_class in (ProfileV1,ProfileV2) else Mode),('bands',Band)):
        for i,row in enumerate(profile[key]):
            values=dict(row)
            if key=='modes' and profile_class in (ProfileV1,ProfileV2):values.pop('attack_seconds',None)
            getattr(native,key)[i]=cls(**values)
    if profile_class is Profile:
        for i,c in enumerate(profile.get('contours',[])):
            native.contours[i]=Contour(count=len(c['seconds']),low_hz=c['low_hz'],high_hz=c['high_hz'],
                seconds=(ct.c_double*8)(*c['seconds']),gain=(ct.c_double*8)(*c['gain']))
    return native

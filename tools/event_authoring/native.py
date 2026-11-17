"""Non-RT authoring bridge to the actual C pool; no vehicle ABI changes."""
import ctypes as ct
import math
import json
from pathlib import Path
import numpy as np
from .audio import sha
from .model import KINDS,validate


from .contract import Profile,Request,pack_profile


DEFAULTS=dict(seconds=2.,seed=27431,strength=1.,pitch=1.,decay=1.,texture=1.,hold_seconds=.8)


def controls(value):
    if not isinstance(value,dict) or set(value)-set(DEFAULTS):raise ValueError('未知事件试听参数')
    p=dict(DEFAULTS,**value)
    for key,lo,hi in [('seconds',.06,12),('strength',0,4),('pitch',.5,2),
                      ('decay',.25,4),('texture',0,2),('hold_seconds',0,12)]:
        v=p[key]
        if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or not lo<=v<=hi:
            raise ValueError('事件试听参数无效：'+key)
    if type(p['seed']) is not int or not 1<=p['seed']<=4294967295:raise ValueError('种子需为1–4294967295的整数')
    return p


class Renderer:
    def __init__(self,repo):
        self.path=Path(repo)/'build-event-synth-v4/bin/Release/vsl_event_author_bridge.dll'
        if not self.path.is_file():raise ValueError('请先运行 Build-Event-Designer.ps1 构建事件C试听核')
        self.lib=ct.CDLL(str(self.path));self.identity=sha(self.path)
        binding=self.path.with_name('event-author-build.json')
        if not binding.is_file():raise ValueError('缺少事件构建来源清单，请运行 Build-Event-Designer.ps1')
        built=json.loads(binding.read_text(encoding='utf-8-sig'));self.sources=built['sources']
        if built.get('schema')!='vsl.event-author-build/1' or built['dll_sha256']!=self.identity or any(
            sha(Path(repo)/name)!=digest for name,digest in self.sources.items()):
            raise ValueError('事件C源码或试听DLL已变化，请重新运行 Build-Event-Designer.ps1')
        for key in ('abi','profile_size','request_size'):
            fn=getattr(self.lib,'vsl_event_author_'+key);fn.argtypes=[];fn.restype=ct.c_uint
        if (self.lib.vsl_event_author_abi(),self.lib.vsl_event_author_profile_size(),
            self.lib.vsl_event_author_request_size())!=(4,ct.sizeof(Profile),ct.sizeof(Request)):
            raise ValueError('事件提参桥接ABI不匹配')
        self.fn=self.lib.vsl_event_author_render
        self.fn.argtypes=[ct.POINTER(Profile),ct.POINTER(Request),ct.c_uint,ct.c_uint,ct.POINTER(ct.c_float)]
        self.fn.restype=ct.c_int

    def render(self,profile,kind,values):
        validate(profile);p=controls(values)
        if kind not in KINDS:raise ValueError('未知事件类型')
        native=pack_profile(profile)
        request=Request(id=1,type=KINDS.index(kind),priority=100,seed=p['seed'],
            **{k:p[k] for k in ('strength','pitch','decay','texture')})
        frames=round(p['seconds']*48000);audio=np.zeros(frames,dtype=np.float32)
        release=round(p['hold_seconds']*48000) if profile['gated'] else 0xffffffff
        if not self.fn(ct.byref(native),ct.byref(request),frames,release,audio.ctypes.data_as(ct.POINTER(ct.c_float))):
            raise ValueError('C事件声源拒绝参数；至少需要一个模态或噪声频带')
        if not np.isfinite(audio).all():raise ValueError('C事件输出包含无效采样')
        peak=float(np.max(abs(audio)));rms=float(np.sqrt(np.mean(audio.astype(float)**2)))
        return audio,dict(renderer_sha256=self.identity,renderer_abi=4,frames=frames,sample_rate=48000,
            renderer_sources=self.sources,
            channels=1,peak=peak,rms=rms,overload=peak>=1,monitor_gain=.25,
            release_frame=release if profile['gated'] else None,
            processing='actual event_synth C pool; fixed 0.25 monitor gain; no normalization, room or PCM source')

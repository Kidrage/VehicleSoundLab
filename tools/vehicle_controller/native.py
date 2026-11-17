"""Typed, version-checked bridge to the modular C source generator."""
import ctypes as C
import hashlib
import json
import tempfile
from pathlib import Path
from .identity import voices
from .event_profiles import validate_overrides
from event_authoring.contract import Profile,ProfileV1,ProfileV2,ProfileV3,pack_profile
from . import startup,event_policy as policy,dna_bank as dna,catalog_assets


class Signals(C.Structure):
    _fields_=[('source',C.c_int),('valid',C.c_uint),('sequence',C.c_uint64),
              ('speed_mps',C.c_double),('acceleration_mps2',C.c_double),('tire_slip',C.c_double)]


EVENT_KINDS=('engage','crank','catch','afterfire','shift','disengage','stop')


class EventControl(C.Structure):
    _fields_=[('enabled',C.c_int),('manual_type',C.c_int),('manual_sequence',C.c_uint64)]+[
        (key,C.c_double) for key in ('gain','pitch','decay','texture')]+[('levels',C.c_double*7)]


class EventNotice(C.Structure):
    _fields_=[(key,C.c_uint64) for key in ('id','frame','requested_frame')]+[
        (key,C.c_uint) for key in ('type','slot','action','reason')]


class DnaControl(C.Structure):
    _fields_=[(k,C.c_double) for k in ('line','air','motion','idle_blend','air_continuity','pitch_follow')]+[
        ('line_state',C.c_double*6),('air_state',C.c_double*6)]


class Control(C.Structure):
    _fields_=[(key,C.c_int) for key in ('mode','ignition','start_id','gear','automatic','backfire')]+[
        (key,C.c_double) for key in ('rpm','load','throttle','brake','gain','detail','legacy_event_gain',
        'low_mix','coherent_low_gain','resonant_gain','residual_gain','intake_gain','mechanical_gain',
        'air_gain','road_gain','wind_gain','startup_gain','catch_gain','idle_mix','idle_motion','idle_detail')]+[('input',Signals),('events',EventControl),('dna_unified',C.c_int),('dna',DnaControl)]


class Telemetry(C.Structure):
    _fields_=[('frame',C.c_uint64)]+[(key,C.c_double) for key in
        ('rpm','speed_mps','acceleration_mps2','load','root_hz','gain','idle_weight')]+[
        (key,C.c_int) for key in ('gear','lifecycle','operating','coverage')]+[
        (key,C.c_uint) for key in ('shifts','overruns','legacy_hits')]+[
        ('input_source',C.c_int),('input_stale',C.c_int),('tire_slip',C.c_double),('signal_sequence',C.c_uint64)]+[
        (key,C.c_uint) for key in ('event_active','event_started','event_rejected','event_replaced','event_queue','event_overflow','event_log_lost','event_peak')]


class DnaState(C.Structure):
    _fields_=[('available_mask',C.c_uint),('weight',C.c_double*4),
              ('target',C.c_double*4),('coverage',C.c_int*4)]


def unpack(value):
    if isinstance(value,C.Array):return list(value)
    if isinstance(value,C.Structure):return {key:unpack(getattr(value,key)) for key,_ in value._fields_}
    return value


def pack(data):
    def convert(kind,item):
        if issubclass(kind,C.Structure):
            if not isinstance(item,dict) or set(item)!=set(key for key,_ in kind._fields_):raise ValueError('控制字段不完整或版本不匹配')
            value=kind()
            for key,field in kind._fields_:setattr(value,key,convert(field,item[key]))
            return value
        if issubclass(kind,C.Array):
            if not isinstance(item,list) or len(item)!=kind._length_:raise ValueError('事件电平表长度错误')
            return kind(*(convert(kind._type_,x) for x in item))
        if kind in (C.c_int,C.c_uint,C.c_uint64):
            low,high=(-2**31,2**31-1) if kind is C.c_int else (0,2**(8*C.sizeof(kind))-1)
            if not isinstance(item,int) or not low<=item<=high:raise ValueError('控制整数超出范围')
        return item
    return convert(Control,data)


class Bridge:
    def __init__(self,repo,library=None):
        self.repo=Path(repo)
        self.path=Path(library) if library is not None else Path(repo)/'build-vehicle-source-v15/bin/Release/vsl_source_bridge.dll'
        if not self.path.is_file(): raise RuntimeError('请先运行 Build-Vehicle-Source.ps1')
        self.lib=C.CDLL(str(self.path))
        signatures={
            'abi':([],C.c_uint),'control_size':([],C.c_uint),'telemetry_size':([],C.c_uint),
            'startup_size':([],C.c_uint),
            'startup_set':([C.c_void_p,C.POINTER(startup.Response)],C.c_int),
            'startup_get':([C.c_void_p,C.POINTER(startup.Response)],C.c_int),
            'event_notice_size':([],C.c_uint),'event_mask':([],C.c_uint),'event_bank_identity':([],C.c_char_p),
            'event_profile_size':([],C.c_uint),'event_profile':([C.c_void_p,C.c_uint,C.c_void_p],C.c_int),
            'events':([C.c_void_p,C.POINTER(EventNotice),C.c_uint],C.c_uint),
            'catalog_count':([],C.c_uint),'catalog_name':([C.c_int],C.c_char_p),'catalog_key':([C.c_int],C.c_char_p),
            'open':([C.c_int],C.c_void_p),'close':([C.c_void_p],None),
            'controls':([C.c_void_p,C.POINTER(Control)],C.c_int),
            'set':([C.c_void_p,C.POINTER(Control)],C.c_int),
            'state':([C.c_void_p,C.POINTER(Telemetry)],C.c_int),'channels':([],C.c_uint),
            'capabilities':([C.c_void_p],C.c_uint),'stem_name':([C.c_uint],C.c_char_p),
            'stem_channels':([C.c_uint],C.c_uint),
            'process':([C.c_void_p,C.POINTER(C.c_float),C.POINTER(C.c_float),C.c_uint],C.c_int)}
        for key,(args,result) in signatures.items():
            function=getattr(self.lib,'vsl_source_'+key);function.argtypes=args;function.restype=result;setattr(self,key,function)
        self.profile_class=ProfileV1 if self.abi()==5 else ProfileV2 if self.abi()<10 else ProfileV3 if self.abi()==10 else Profile
        if self.abi()!=12 or self.startup_size()!=C.sizeof(startup.Response) or self.control_size()!=C.sizeof(Control) or self.telemetry_size()!=C.sizeof(Telemetry) or self.event_notice_size()!=C.sizeof(EventNotice) or self.event_profile_size()!=C.sizeof(self.profile_class):
            raise RuntimeError('C/Python 接口版本不一致，请重新构建声源模块')
        if self.abi()>=7:
            for key,args,result in (
                ('event_policy_size',[],C.c_uint),('event_policy_stats_size',[],C.c_uint),
                ('event_policy_set',[C.c_void_p,C.POINTER(policy.Policy)],C.c_int),
                ('event_policy_get',[C.c_void_p,C.POINTER(policy.Policy)],C.c_int),
                ('event_policy_stats',[C.c_void_p,C.POINTER(policy.Stats)],C.c_int)):
                function=getattr(self.lib,'vsl_source_'+key);function.argtypes=args;function.restype=result;setattr(self,key,function)
            if self.event_policy_size()!=C.sizeof(policy.Policy) or self.event_policy_stats_size()!=C.sizeof(policy.Stats):
                raise RuntimeError('C/Python 事件触发配方布局不一致')
        if self.abi()>=8:
            self.open_dna=self.lib.vsl_source_open_dna
            self.open_dna.argtypes=[C.c_int,C.POINTER(C.c_char_p),C.c_uint,C.c_double,C.c_uint64,C.c_uint]
            self.open_dna.restype=C.c_void_p
        if self.abi()>=9:
            for key,args,result in (
                ('open_state_dna',[C.c_int,C.POINTER(C.c_char_p),C.POINTER(C.c_uint),C.c_double,C.c_uint64,C.c_uint,C.c_double],C.c_void_p),
                ('dna_state_size',[],C.c_uint),('dna_state',[C.c_void_p,C.POINTER(DnaState)],C.c_int)):
                function=getattr(self.lib,'vsl_source_'+key);function.argtypes=args;function.restype=result;setattr(self,key,function)
            if self.dna_state_size()!=C.sizeof(DnaState):raise RuntimeError('C/Python DNA状态布局不一致')
        bank=json.loads((self.repo/'voices/events_v1/profiles.json').read_text(encoding='utf-8'))
        identity=hashlib.sha256(json.dumps(bank,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode('utf-8')).hexdigest()
        if self.event_bank_identity().decode()!=identity:raise RuntimeError('事件参数已变化，请重新编译 C 声源库')
        self.event_bank_sha256=identity;self.event_available_mask=self.event_mask()
        self.event_profiles=bank['profiles']
        self.sha256=hashlib.sha256(self.path.read_bytes()).hexdigest()
        self.voices_sha256,self.voice_manifest=voices(repo)
        if self.abi()>=9:
            self.catalog_assets_sha256,self.catalog_assets=catalog_assets.inventory(repo)
        self.catalog=[dict(id=k,name=self.catalog_name(k).decode('utf-8'),key=self.catalog_key(k).decode('utf-8'))
                      for k in range(self.catalog_count())]
        self.stems=[]
        for k in range(64):
            channels=self.stem_channels(k)
            if not channels: break
            self.stems.append(dict(id=k,name=self.stem_name(k).decode('utf-8'),channels=channels))
        if sum(row['channels'] for row in self.stems)!=self.channels(): raise RuntimeError('分轨布局不一致')
        handle=self.open(0)
        if not handle:raise RuntimeError('无法读取 C 默认启动响应')
        try:
            response=startup.Response()
            if not self.startup_get(handle,C.byref(response)):raise RuntimeError('无法读取 C 默认启动响应')
            self.startup_defaults=startup.validate(unpack(response))
            self.event_policy_defaults=policy.validate(policy.defaults())
            if self.abi()>=7:
                configuration=policy.Policy()
                if not self.event_policy_get(handle,C.byref(configuration)):raise RuntimeError('无法读取 C 默认事件触发配方')
                self.event_policy_defaults=policy.validate(unpack(configuration))
        finally:self.close(handle)
        catalog_assets.live(self)

    def initial(self,selection,dna_bank=None):
        with Engine(self,selection,dna_bank=dna_bank) as engine: return engine.controls,engine.features

    def authored(self,selection,bank):
        bank=dna.supported(bank,self.abi())
        groups=dna.banks(bank)
        with tempfile.TemporaryDirectory(prefix='vsl-dna-') as temporary:
            paths=[]
            for k,row in enumerate(row for group in groups for row in group):
                path=Path(temporary)/f'{k}.model';path.write_bytes(row['model'].encode('ascii'))
                paths.append(str(path).encode('utf-8'))
            if bank['schema']==dna.STATE_SCHEMA:
                return self.open_state_dna(selection,(C.c_char_p*len(paths))(*paths),(C.c_uint*4)(*(len(g) for g in groups)),
                    bank['root_per_rpm'],bank['seed'],bank['align_orders'],bank['transition_seconds'])
            return self.open_dna(selection,(C.c_char_p*len(paths))(*paths),len(paths),
                bank['root_per_rpm'],bank['seed'],bank['align_orders'])


class Engine:
    def __init__(self,bridge,selection,event_overrides=None,startup_response=None,event_policy=None,dna_bank=None):
        bank=dna.supported(dna_bank,bridge.abi())
        overrides=validate_overrides(event_overrides)
        response=startup.configuration(bridge,startup_response)
        configuration=policy.configuration(bridge,event_policy)
        if voices(bridge.repo)[0]!=bridge.voices_sha256:raise RuntimeError('参数库已更新，请重开控制窗口以采用新版本')
        catalog_assets.live(bridge)
        self.bridge=bridge;self.handle=bridge.authored(selection,bank) if bank is not None else bridge.open(selection)
        if not self.handle: raise RuntimeError('C 声源参数载入失败')
        if voices(bridge.repo)[0]!=bridge.voices_sha256:
            self.close();raise RuntimeError('载入过程中参数库发生变化，请重试')
        try:catalog_assets.live(bridge)
        except Exception:
            self.close();raise
        self.mix=(C.c_float*(1024*2))();self.stems=(C.c_float*(1024*bridge.channels()))()
        self.solo=(C.c_float*(1024*2))();control=Control()
        self.notice_buffer=(EventNotice*128)();self.last_events=[]
        if not bridge.controls(self.handle,C.byref(control)): self.close();raise RuntimeError('无法读取 C 参数')
        self.controls=unpack(control);self.features=bridge.capabilities(self.handle);self.frame=0
        try:
            native_response=startup.Response(**response)
            if not bridge.startup_set(self.handle,C.byref(native_response)):raise ValueError('C拒绝启动响应参数')
            if bridge.abi()>=7:
                native_policy=policy.Policy(**configuration)
                if not bridge.event_policy_set(self.handle,C.byref(native_policy)):raise ValueError('C拒绝事件触发配方')
                copied=policy.Policy()
                if not bridge.event_policy_get(self.handle,C.byref(copied)) or unpack(copied)!=configuration:
                    raise RuntimeError('C事件触发配方读回不一致')
            for kind,doc in overrides.items():
                profile=pack_profile(doc['parameters'],bridge.profile_class)
                if not bridge.event_profile(self.handle,EVENT_KINDS.index(kind),C.byref(profile)):
                    raise ValueError('C拒绝事件覆盖参数：'+kind)
        except Exception:self.close();raise
        self.event_overrides=overrides
        self.startup_response=response
        self.event_policy=configuration
        self.dna_bank=bank
        if bank is not None:
            try:self.set(dict(self.controls,detail=bank['detail']))
            except Exception:self.close();raise

    def close(self):
        if self.handle: self.bridge.close(self.handle);self.handle=None

    def __enter__(self): return self
    def __exit__(self,*args): self.close()

    def set(self,data):
        value=pack(data)
        if not self.bridge.set(self.handle,C.byref(value)): raise ValueError('C 拒绝控制参数：请检查范围或信号序号')
        self.controls=unpack(value)

    def state(self):
        value=Telemetry()
        if not self.bridge.state(self.handle,C.byref(value)): raise RuntimeError('无法读取 C 状态')
        return unpack(value)

    def policy_stats(self):
        value=policy.Stats()
        if self.bridge.abi()>=7 and not self.bridge.event_policy_stats(self.handle,C.byref(value)):
            raise RuntimeError('无法读取事件触发统计')
        return unpack(value)

    def dna_state(self):
        if self.bridge.abi()<9:return dict(available_mask=1,weight=[1.,0.,0.,0.],target=[1.,0.,0.,0.],coverage=[self.state()['coverage'],0,0,0])
        value=DnaState()
        if not self.bridge.dna_state(self.handle,C.byref(value)):raise RuntimeError('无法读取DNA状态混合')
        return unpack(value)

    def process(self,frames=480,solo=-1):
        if not 0<frames<=1024: raise ValueError('音频块需为 1–1024 帧')
        if not self.bridge.process(self.handle,self.mix,self.stems,frames): raise RuntimeError('C 声源生成失败')
        self.frame+=frames
        count=self.bridge.events(self.handle,self.notice_buffer,128)
        self.last_events=[unpack(self.notice_buffer[k]) for k in range(count)]
        if solo<0: return C.string_at(self.mix,frames*8)
        if solo>=len(self.bridge.stems): raise ValueError('无效分轨')
        stem=self.bridge.stems[solo];offset=sum(row['channels'] for row in self.bridge.stems[:solo]);width=self.bridge.channels()
        weight=1 if stem['channels']==2 or stem['name']=='legacy_event' else .7071067811865475
        for n in range(frames):
            self.solo[2*n]=self.stems[n*width+offset]*weight
            self.solo[2*n+1]=self.stems[n*width+offset+(stem['channels']==2)]*weight
        return C.string_at(self.solo,frames*8)

"""Archived V16 research audition; not imported by the production App.

Standard library only. Profiles are loaded/copied before audio. C produces,
weights and mixes each block; no original or rendered audio is played back.
"""
import ctypes as C
import hashlib,json,time,threading
from copy import deepcopy
from pathlib import Path
from startup_character_v1.contract import Ridge,pack as pack_ridges
from startup_rotation_v1.contract import Profile,pack as pack_rotation
from vehicle_controller.native import Engine
from vehicle_controller.device import Output

class Gesture(C.Structure):
    _fields_=[('level',C.c_double),('core',C.c_double),('texture',C.c_double),('count',C.c_uint),('knot',C.c_double*4),('pitch',C.c_double*4)]
class Timeline(C.Structure):
    _fields_=[('start',C.c_double),('duration',C.c_double*3),('handoff',C.c_double),('reference_gain',C.c_double),('rotation_scale',C.c_double),('gesture',Gesture*3)]

class Scene:
    def __init__(self,repo,previous=False):
        self.handles=[];self.frame=0;self.repo=Path(repo);self.previous=previous
        folder=self.repo/'experiments/startup_character_v1/runtime_bank'
        manifest=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
        for row in manifest:
            path=(folder/row['path']).resolve()
            if not path.is_relative_to(folder.resolve()) or hashlib.sha256(path.read_bytes()).hexdigest()!=row['sha256']:raise ValueError('启动试听参数校验失败')
        bank=json.loads((folder/'bank.json').read_text(encoding='utf-8'));self.bank=bank
        lib=self.repo/'build-startup-character-v5/Release/startup_character_bridge.dll'
        self.lib=C.CDLL(str(lib));d=C.POINTER(C.c_double);f=C.POINTER(C.c_float)
        self.lib.sc_open.argtypes=[C.c_char_p]*3+[d,C.c_double,C.c_uint64];self.lib.sc_open.restype=C.c_void_p
        self.lib.sc_close.argtypes=[C.c_void_p]
        self.lib.sc_configure_ridges.argtypes=[C.c_void_p,C.POINTER(Ridge),C.c_uint,C.c_uint,C.c_double,C.c_double,C.c_uint64]
        self.lib.sc_configure_rotation.argtypes=[C.c_void_p,C.POINTER(Profile),C.c_uint64]
        self.lib.sc_timeline_size.restype=C.c_uint
        if self.lib.sc_timeline_size()!=C.sizeof(Timeline):raise ValueError('启动试听C接口版本不匹配')
        self.lib.sc_scene_process.argtypes=[C.POINTER(C.c_void_p),C.POINTER(Timeline),C.c_uint64,f,f,f,C.c_uint]
        recipe=bank['recipe']['base_recipe'];self.timeline=Timeline();t=self.timeline
        t.start=recipe['start_seconds'];t.duration[:]=[recipe['prelude_seconds'],recipe['crank_seconds'],recipe['catch_rise_seconds']+recipe['catch_settle_seconds']]
        t.handoff=recipe['handoff_seconds'];t.reference_gain=recipe['reference_gain'];t.rotation_scale=1 if previous else bank['recipe']['rotation_scale']
        self.frames=round(recipe['seconds']*48000)
        self.control=deepcopy(bank['base']['control']);self.response=deepcopy(bank['base']['startup_response'])
        self.ignition=round(t.start*48000);self.start=round((t.start+t.duration[0])*48000)
        try:
            for k,name in enumerate(('prelude','crank','catch')):
                profile=bank['profiles']['previous' if previous and name=='crank' else name]
                seed=(97346 if previous else 142867) if name=='crank' else 96337+1009*k
                paths=[str((folder/row['path']).resolve()).encode('utf-8') for row in profile['profiles']]
                env=(C.c_double*9)(*profile['envelope']);handle=self.lib.sc_open(*paths,env,profile['variation'],seed)
                if not handle:raise ValueError('启动声源初始化失败')
                self.handles.append(handle)
                if 'rotation' in profile:
                    model=pack_rotation(profile['rotation']);ok=self.lib.sc_configure_rotation(handle,C.byref(model),seed)
                else:
                    rows=pack_ridges(profile['ridges']);ok=self.lib.sc_configure_ridges(handle,rows,len(rows),profile['reference_frames'],profile['ridge_variation'],profile['ridge_pitch'],seed)
                if not ok:raise ValueError('启动OSC参数被C拒绝')
                row=recipe[name];g=t.gesture[k];g.level=row['level'];g.core=row['core'];g.texture=row['texture'];g.count=len(row['pitch'])
                for j,(p,v) in enumerate(zip(row['pitch_knots'],row['pitch'])):g.knot[j]=p;g.pitch[j]=v
        except Exception:self.close();raise
        self.voices=(C.c_void_p*3)(*self.handles);self.mix=(C.c_float*2048)();self.parts=(C.c_float*8192)()

    def close(self):
        for handle in self.handles:self.lib.sc_close(handle)
        self.handles=[]
    def __enter__(self):return self
    def __exit__(self,*args):self.close()
    def adopt(self,engine):
        control=deepcopy(self.control);control.update(ignition=int(engine.frame>=self.ignition),start_id=int(engine.frame>=self.start));engine.set(control)
    def process(self,base,frames):
        if not self.lib.sc_scene_process(self.voices,C.byref(self.timeline),self.frame,base,self.mix,self.parts,frames):raise RuntimeError('启动试听合成失败')
        self.frame+=frames;return C.string_at(self.mix,frames*8)

class AuditionHost:
    """Owns only this seven-second audition; it cannot create a normal take."""
    is_audition=True
    def __init__(self,bridge,previous=False):
        self.bridge=bridge;self.previous=previous;self.lock=threading.Lock();self.stop_event=threading.Event();self.thread=None;self.muted=False
        self.status=dict(active=False,starting=True,error=None,audition=True)
    def update(self,control,solo=-1,muted=False):
        with self.lock:self.muted=muted
    def snapshot(self):
        with self.lock:return deepcopy(self.status)
    def take_snapshot(self):raise ValueError('启动A/B试听使用独立声源配方；普通行程请用“启动”录制')
    def start(self):
        self.thread=threading.Thread(target=self.run,name='StartupAuditionAudio',daemon=True);self.thread.start()
    def stop(self):self.stop_event.set()
    def run(self):
        try:
            with Scene(self.bridge.repo,self.previous) as scene,Engine(self.bridge,0,startup_response=scene.response) as engine,Output() as device:
                underflows=0;maximum=0
                while engine.frame<scene.frames and not self.stop_event.is_set():
                    if not device.ready():self.stop_event.wait(.001);continue
                    if device.submitted>device.count and not device.queued():underflows+=1
                    started=time.perf_counter();pieces=[];done=0
                    # 240frame controls match the frozen C reference, even
                    # though the device consumes480frames per buffer.
                    count=min(device.frames,scene.frames-engine.frame)
                    while done<count:
                        scene.adopt(engine);n=min(240-engine.frame%240,count-done)
                        engine.process(n);pieces.append(scene.process(engine.mix,n));done+=n
                    data=b''.join(pieces);elapsed=time.perf_counter()-started;maximum=max(maximum,elapsed/.01)
                    with self.lock:muted=self.muted
                    device.write(bytes(device.frames*8) if muted else data+bytes(device.frames*8-len(data)))
                    state=engine.state();state.update(active=True,starting=False,error=None,audition=True,underflows=underflows,pc_block_load=elapsed/.01,pc_max_block_load=maximum,event_policy_stats=engine.policy_stats(),dna_state=engine.dna_state())
                    with self.lock:self.status=state
                if not self.stop_event.is_set():device.drain()
        except Exception as error:
            with self.lock:self.status.update(error=str(error),starting=False)
        finally:
            with self.lock:self.status.update(active=False,starting=False)

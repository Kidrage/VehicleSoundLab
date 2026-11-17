"""Single audio owner; UI exchanges controls and snapshots, never native state."""
from copy import deepcopy
import threading
import time
from .device import Output
from .native import Engine
from . import take,startup,event_policy as policy,dna_bank as dna


class Host:
    def __init__(self,bridge,selection,control,replay=None,event_overrides=None,startup_response=None,event_policy=None,dna_bank=None):
        self.bridge=bridge;self.selection=selection;self.control=deepcopy(control);self.replay=replay
        self.lock=threading.Lock();self.stop_event=threading.Event();self.thread=None
        self.solo=-1;self.muted=False;self.status=dict(active=False,starting=True,error=None)
        self.event_overrides=deepcopy(replay['event_overrides'] if replay else event_overrides or {})
        self.startup_response=startup.configuration(bridge,replay['startup_response'] if replay else startup_response)
        self.event_policy=policy.configuration(bridge,replay.get('event_policy') if replay else event_policy)
        self.dna_bank=dna.validate(replay.get('dna_bank') if replay else dna_bank)
        self.record=deepcopy(replay) if replay else take.create(bridge,selection,control,self.event_overrides,self.startup_response,self.event_policy,self.dna_bank)
        self.record['frames']=0
        # A planned replay may have no notices yet. Record what this execution
        # actually generated instead of inheriting (or duplicating) input notices.
        self.record['source_events']=[]

    def start(self):
        self.thread=threading.Thread(target=self.run,name='VehicleSourceAudio',daemon=True);self.thread.start()

    def update(self,control,solo=-1,muted=False):
        with self.lock: self.control=deepcopy(control);self.solo=solo;self.muted=muted

    def snapshot(self):
        with self.lock: return deepcopy(self.status)

    def take_snapshot(self):
        with self.lock:
            value=deepcopy(self.record)
            value['events']=[event for event in value['events'] if event['frame']<value['frames']]
            value['source_events']=[event for event in value.get('source_events',[]) if event['frame']<value['frames'] or event['action']==2 and event['frame']==value['frames']]
            return value

    def stop(self): self.stop_event.set()

    def run(self):
        try:
            with Engine(self.bridge,self.selection,self.event_overrides,self.startup_response,self.event_policy,self.dna_bank) as engine,Output() as device:
                engine.set(self.replay['initial'] if self.replay else self.control)
                event_index=0;underflows=0;max_load=0
                while not self.stop_event.is_set():
                    if not device.ready(): self.stop_event.wait(.001);continue
                    with self.lock: control=deepcopy(self.control);solo=self.solo;muted=self.muted
                    if device.submitted>device.count and not device.queued(): underflows+=1
                    started=time.perf_counter()
                    if self.replay:
                        if engine.frame>=self.replay['frames']: device.drain();break
                        data,event_index=take.replay_block(engine,self.replay,event_index,device.frames,solo)
                        data+=bytes(device.frames*8-len(data))
                    else:
                        if control!=engine.controls: engine.set(control)
                        with self.lock: take.append(self.record,engine.frame,engine.controls)
                        data=engine.process(device.frames,solo)
                    elapsed=time.perf_counter()-started;max_load=max(max_load,elapsed/.01)
                    device.write(bytes(len(data)) if muted else data)
                    state=engine.state();state.update(active=True,starting=False,error=None,underflows=underflows,
                        pc_block_load=elapsed/.01,pc_max_block_load=max_load,replay=self.replay is not None,event_policy_stats=engine.policy_stats(),dna_state=engine.dna_state())
                    if self.replay:state['adopted_control']=deepcopy(engine.controls)
                    with self.lock:
                        self.status=state;self.record['frames']=engine.frame
                        self.record['source_events'].extend(engine.last_events)
        except Exception as error:
            with self.lock: self.status.update(error=str(error),starting=False)
        finally:
            with self.lock: self.status.update(active=False,starting=False)

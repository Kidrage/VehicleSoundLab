"""Paired actual Windows C-boundary cycles, frozen V19 versus V20."""
import argparse
from copy import deepcopy
import ctypes as C
import json
from pathlib import Path
import statistics
from vehicle_controller.native import Bridge,Engine
from vehicle_controller.startup_sound import defaults as sd
from vehicle_controller.afterfire import defaults as ad

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():raise ValueError('Preserve earlier measurements')
    repo=Path(__file__).resolve().parents[1];new=Bridge(repo)
    old=Bridge(repo,repo/'build-vehicle-source-v16/bin/Release/vsl_source_bridge.dll')
    kernel=C.WinDLL('kernel32',use_last_error=True);kernel.GetCurrentThread.restype=C.c_void_p
    kernel.QueryThreadCycleTime.argtypes=[C.c_void_p,C.POINTER(C.c_uint64)];kernel.QueryThreadCycleTime.restype=C.c_int
    thread=kernel.GetCurrentThread()
    def cycles():
        n=C.c_uint64();assert kernel.QueryThreadCycleTime(thread,C.byref(n));return n.value
    def run(b,scene):
        c,f=b.initial(0);c=sd(c,b.event_available_mask,f);c,overrides,policy=ad(b,0,c,f)
        c.update(mode=0,rpm=4000,load=-.2 if scene=='coast' else .6,ignition=1,start_id=1)
        if scene!='four_voices':c['events']['enabled']=0
        # Single-event manual requests deliberately sustain the SAME four slots.
        policy.update(afterfire_min_count=1,afterfire_max_count=1)
        with Engine(b,0,overrides,event_policy=policy) as e:
            e.set(c)
            for _ in range(300):e.process(480)
            total=0;blocks=[]
            for block in range(300):
                begin=cycles()
                if scene=='four_voices' and block%10==0:
                    for _ in range(4):
                        c['events'].update(manual_type=3,manual_sequence=c['events']['manual_sequence']+1);e.set(c)
                assert b.process(e.handle,e.mix,e.stems,480);e.frame+=480
                used=cycles()-begin;total+=used;blocks.append(used)
            return dict(thread_cycles=total,max_block_cycles=max(blocks),peak_voices=e.state()['event_peak'])
    scenes={}
    for scene in ('power','coast','four_voices'):
        pairs=[]
        for repeat in range(5):
            row={}
            for b in ((old,new) if repeat%2==0 else (new,old)):row['old' if b is old else 'new']=run(b,scene)
            row['change_percent']=(row['new']['thread_cycles']/row['old']['thread_cycles']-1)*100;pairs.append(row)
        values=[r['change_percent'] for r in pairs]
        scenes[scene]=dict(pairs=pairs,median_change_percent=statistics.median(values),min_change_percent=min(values),max_change_percent=max(values))
        print(scene,scenes[scene]['median_change_percent'],flush=True)
    report=dict(schema='vsl.coast-afterfire-cost/1',old_sha256=old.sha256,new_sha256=new.sha256,
        repeats=5,seconds_per_run=3,scenes=scenes,
        note='Windows thread cycles around C processing and scheduled four-onset batches including control calls. Not ADI MCPS, a hard real-time peak bound or zero-cycle proof. Burst count raises duty cycle; simultaneous capacity remains four. Full-burst queue preparation is not equivalent to this sustained-voice probe.')
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2),encoding='utf-8')

if __name__=='__main__':main()

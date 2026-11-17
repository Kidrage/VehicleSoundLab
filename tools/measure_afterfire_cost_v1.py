"""Paired Windows thread-cycle counts; no ADI/MCPS extrapolation."""
import argparse
from copy import deepcopy
import ctypes as C
import json
from pathlib import Path
import statistics
import time
from vehicle_controller.native import Bridge,Engine
from vehicle_controller.startup_sound import defaults as startup_defaults
from vehicle_controller.afterfire import defaults as afterfire_defaults


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    if args.output.exists():raise ValueError('Refuse to overwrite an earlier measurement')
    b=Bridge(Path(__file__).resolve().parents[1]);ctrl,f=b.initial(0)
    ctrl=startup_defaults(ctrl,b.event_available_mask,f);ctrl,overrides,policy=afterfire_defaults(b,0,ctrl,f)
    kernel=C.WinDLL('kernel32',use_last_error=True)
    kernel.GetCurrentThread.restype=C.c_void_p
    kernel.QueryThreadCycleTime.argtypes=[C.c_void_p,C.POINTER(C.c_uint64)];kernel.QueryThreadCycleTime.restype=C.c_int
    thread=kernel.GetCurrentThread()
    def cycles():
        value=C.c_uint64()
        if not kernel.QueryThreadCycleTime(thread,C.byref(value)):raise C.WinError(C.get_last_error())
        return value.value
    def run(enabled,dense):
        c=deepcopy(ctrl);c.update(mode=0,rpm=4000,load=.6,ignition=1,start_id=1)
        c['events']['enabled']=int(enabled)
        with Engine(b,0,overrides if enabled else {},event_policy=policy) as e:
            e.set(c)
            for _ in range(300):e.process(480)
            total=wall=0
            for block in range(300):
                if enabled and dense and block%22==0:
                    for _ in range(4):
                        c['events'].update(manual_type=3,manual_sequence=c['events']['manual_sequence']+1);e.set(c)
                start=time.perf_counter_ns();begin=cycles()
                assert b.process(e.handle,e.mix,e.stems,480)
                total+=cycles()-begin;wall+=time.perf_counter_ns()-start;e.frame+=480
            return dict(thread_cycles=total,wall_ms=wall/1e6,peak_voices=e.state()['event_peak'])
    result={}
    for name,dense in (('no_event',False),('four_active',True)):
        pairs=[]
        for repeat in range(5):
            row={}
            for enabled in ((False,True) if repeat%2==0 else (True,False)):row[str(enabled)]=run(enabled,dense)
            row['cycle_change_percent']=(row['True']['thread_cycles']/row['False']['thread_cycles']-1)*100
            pairs.append(row)
        deltas=[row['cycle_change_percent'] for row in pairs]
        result[name]=dict(pairs=pairs,median_paired_cycle_change_percent=statistics.median(deltas),
                          min_paired_percent=min(deltas),max_paired_percent=max(deltas))
    value=dict(schema='vsl.afterfire-cost-cycles/1',bridge_sha256=b.sha256,seconds_per_run=3.,
        repeats=5,scenes=result,notes='Windows QueryThreadCycleTime around existing C bridge calls; frequency, scheduling and copy/call costs remain. Four-active is a saturation probe, not normal 1–2-pop duty. No hard realtime, zero-cycle or ADI MCPS guarantee.')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(value,indent=2),encoding='utf-8')
    print(json.dumps({name:{k:v for k,v in row.items() if k!='pairs'} for name,row in result.items()}),flush=True)


if __name__=='__main__':main()

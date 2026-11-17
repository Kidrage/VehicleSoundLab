"""Actual C rendering, isolated-event proof, paired cost and main-app replay."""
import argparse
from copy import deepcopy
import ctypes as C
import json
from pathlib import Path
import statistics
import time
from vehicle_controller.native import Bridge,Engine
from vehicle_controller import take,recipe
from vehicle_controller.startup_sound import defaults as startup_defaults
from vehicle_controller.afterfire import defaults as afterfire_defaults


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--ui',action='store_true');args=p.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    import numpy as np
    import soundfile as sf
    repo=Path(__file__).resolve().parents[1];b=Bridge(repo)
    c,features=b.initial(0);c=startup_defaults(c,b.event_available_mask,features)
    c,overrides,policy=afterfire_defaults(b,0,c,features)
    assert b.sha256=='7d22c302389c34168dfa19a78f810f597178c1891286d3e2b09111c1a9e3efea'
    assert b.voices_sha256=='71ebb2dd4e6b8ea51cc09ebfb474222b748f4e9c3c9c993bd44a39969ad1569a'
    c.update(mode=1,gear=0,automatic=0,ignition=1,start_id=1)
    doc=take.create(b,0,c,overrides,event_policy=policy);doc['frames']=round(8.5*48000)
    changes=[(3.,.95),(4.5,0.),(6.,.8),(7.5,0.)]
    u=deepcopy(c)
    for seconds,throttle in changes:u['throttle']=throttle;take.append(doc,round(seconds*48000),u)
    offsets=np.cumsum([0]+[r['channels'] for r in b.stems])
    def render(value,chunk=480):
        mix=[];stems=[];notices=[];states=[];index=0
        with Engine(b,0,value['event_overrides'],value['startup_response'],value['event_policy']) as e:
            e.set(value['initial'])
            while e.frame<value['frames']:
                while index<len(value['events']) and value['events'][index]['frame']==e.frame:
                    e.set(value['events'][index]['control']);index+=1
                n=min(chunk,value['frames']-e.frame,value['events'][index]['frame']-e.frame if index<len(value['events']) else value['frames'])
                mix.append(np.frombuffer(e.process(n),dtype='<f4').copy().reshape(n,2))
                stems.append(np.ctypeslib.as_array(e.stems)[:n*b.channels()].copy().reshape(n,b.channels()))
                notices.extend(e.last_events);states.append(e.state())
            stats=e.policy_stats()
        return np.concatenate(mix),np.concatenate(stems),notices,states,stats
    print('Render automatic throttle lifts',flush=True)
    mix,stems,notices,states,stats=render(doc)
    starts=[n for n in notices if n['action']==1];assert starts and all(n['type']==3 for n in starts),notices
    assert len(starts)<=4 and max(s['event_active'] for s in states)<=4
    assert np.isfinite(mix).all() and np.max(abs(mix))<.95
    assert stats['opportunities']>=2 and stats['bursts_attempted']>=2 and not stats['unavailable'],stats
    # Disable through the existing driver permission, rather than removing a bus.
    no=deepcopy(doc)
    no['initial']['backfire']=0
    for row in no['events']:row['control']['backfire']=0
    base,bs,bn,_,_=render(no)
    assert not bn and np.array_equal(stems[:,:offsets[12]],bs[:,:offsets[12]])
    assert np.max(abs(bs[:,offsets[12]:]))==0
    event=stems[:,offsets[12]:].sum(axis=1)*2**-.5
    error=float(np.max(abs((mix-base)-event[:,None])));assert error<1e-7,error
    # Sample partition, event identities, manual replay and strict preset storage.
    m2,s2,n2,_,_=render(doc,217)
    assert np.array_equal(mix,m2) and np.array_equal(stems,s2) and notices==n2
    doc['source_events']=notices;path=args.output/'Afterfire.vsltake.json';take.save(path,doc);read=take.read(path,b)
    with Engine(b,0,read['event_overrides'],read['startup_response'],read['event_policy']) as e:
        e.set(read['initial']);pieces=[];index=0
        while e.frame<read['frames']:
            data,index=take.replay_block(e,read,index,min(313,read['frames']-e.frame));pieces.append(data)
    assert b''.join(pieces)==mix.tobytes()
    preset=recipe.create(b,0,c,'踏板驾驶',overrides,event_policy=policy)
    recipe.validate(b,preset);take.save(args.output/'Afterfire.recipe.json',preset)
    # Manual audition is permitted with engine OFF; no startup is smuggled in.
    manual=deepcopy(doc);manual.update(frames=round(2.*48000),events=[],source_events=[])
    manual['initial'].update(ignition=0,start_id=0)
    manual['initial']['events'].update(manual_type=3,manual_sequence=1)
    u=deepcopy(manual['initial']);u['events']['manual_sequence']=2;take.append(manual,round(.65*48000),u)
    u['events']['manual_sequence']=3;take.append(manual,round(1.3*48000),u)
    solo,ss,sn,_,_=render(manual)
    assert len([n for n in sn if n['action']==1])==3 and not np.any(ss[:,:offsets[12]])
    assert not np.array_equal(solo[:5000],solo[31200:36200])
    sf.write(args.output/'Afterfire-isolated.wav',solo,48000,subtype='FLOAT')
    first=starts[0]['frame'];begin=max(0,first-48000);end=min(len(mix),first+2*48000)
    sf.write(args.output/'Throttle-lift.wav',mix[begin:end],48000,subtype='FLOAT')
    sf.write(args.output/'Throttle-lift-off.wav',base[begin:end],48000,subtype='FLOAT')
    report=dict(schema='vsl.procedural-afterfire/1',bridge_sha256=b.sha256,voices_sha256=b.voices_sha256,
        no_runtime_C_changes=True,source_design='engineered candidate, not extracted from an afterfire recording',
        automatic_starts=starts,policy_stats=stats,continuous_19_channels_exact=True,delta_vs_events_error=error,
        partition_and_replay_exact=True,backfire_permission_silences=True,manual_three_fresh_events=True,
        peak=float(np.max(abs(mix))),existing_pool=dict(voices=4,max_modes_per_voice=12,max_bands_per_voice=4),
        preset=dict(modes=4,bands=2,seconds=.22,extra_fir=False,room=False),ui=False)
    print('Measure paired C-boundary CPU time',flush=True)
    def measure(enabled,dense=False):
        ctrl=deepcopy(c);ctrl.update(mode=0,rpm=4000,load=.6)
        ctrl['events']['enabled']=int(enabled)
        with Engine(b,0,overrides if enabled else {},event_policy=policy) as e:
            e.set(ctrl)
            for _ in range(300):e.process(480)
            cpu=wall=0
            for block in range(200):
                if enabled and dense and block%22==0:
                    for _ in range(4):
                        ctrl['events'].update(manual_type=3,manual_sequence=ctrl['events']['manual_sequence']+1);e.set(ctrl)
                start=time.perf_counter_ns();thread=time.thread_time_ns()
                assert b.process(e.handle,e.mix,e.stems,480)
                cpu+=time.thread_time_ns()-thread;wall+=time.perf_counter_ns()-start;e.frame+=480
            return dict(cpu_ms=cpu/1e6,wall_ms=wall/1e6,peak_voices=e.state()['event_peak'])
    measures={}
    for name,dense in (('no_event',False),('four_active',True)):
        pairs=[]
        for repeat in range(3):
            results={}
            for enabled in ((False,True) if repeat%2==0 else (True,False)):results[str(enabled)]=measure(enabled,dense)
            pairs.append(results)
        oldcpu=statistics.median(row['False']['cpu_ms'] for row in pairs)
        newcpu=statistics.median(row['True']['cpu_ms'] for row in pairs)
        measures[name]=dict(pairs=pairs,median_base_cpu_ms=oldcpu,median_candidate_cpu_ms=newcpu,
                            median_cpu_change_percent=(newcpu/oldcpu-1)*100)
        if dense:assert all(row['True']['peak_voices']==4 for row in pairs)
    report['pc_cost']=dict(seconds_per_run=2.,repeats=3,scenes=measures,
        caveat='PC C-boundary CPU timing only, includes call/copy overhead; not ADI MCPS or proof of zero added cycles.')
    (args.output/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    if args.ui:
        print('Verify actual muted app and saved-take replay',flush=True)
        import tkinter as tk
        from vehicle_controller.ui import Window
        from PIL import ImageGrab
        root=tk.Tk();w=Window(root,repo,args.output/'takes');w.muted.set(1)
        def advance(seconds):
            deadline=time.monotonic()+seconds
            while time.monotonic()<deadline:root.update();time.sleep(.005)
        def wait_for(condition,seconds=6):
            deadline=time.monotonic()+seconds
            while not condition() and time.monotonic()<deadline:
                advance(.02)
                assert not w.host.snapshot().get('error'),w.host.snapshot()
            assert condition(),w.host.snapshot()
        try:
            advance(.2);assert 'V19' in root.title() and w.event_panel.available_mask()==8
            assert w.controls()['startup_gain']==.5 and w.controls()['events']['enabled']==1
            w.tabs.select(w.events_page);advance(.2)
            assert not w.event_panel.buttons[3].instate(['disabled'])
            ImageGrab.grab(window=root.winfo_id()).save(args.output/'App-V19-afterfire.png')
            w.event_panel.buttons[3].invoke();wait_for(lambda:w.host.snapshot().get('frame',0)>=16000)
            assert w.running() and w.host.snapshot()['event_started']==1 and w.host.snapshot()['lifecycle']==0
            w.stop();advance(.2);assert not w.last_error,w.last_error
            w.save_take();record=take.read(next((args.output/'takes').glob('*.vsltake.json')),b)
            # Replay an older V18 take without injecting the new default profile.
            older=take.read(Path('E:/VehicleSoundLab/references/analysis/app_headroom_v18/verification2/takes')/next(Path('E:/VehicleSoundLab/references/analysis/app_headroom_v18/verification2/takes').glob('*.vsltake.json')).name,b)
            assert not older['event_overrides']
            w.start(older);wait_for(lambda:not w.running(),older['frames']/48000+5)
            assert not w.running() and not w.event_overrides and not w.host.snapshot().get('error')
            w.start(record);wait_for(lambda:not w.running(),record['frames']/48000+5)
            replay=w.host.snapshot();assert not w.running() and not replay.get('error') and replay['underflows']==0,replay
            assert w.event_overrides==record['event_overrides'] and replay['event_started']==1
            w.load(1);assert not w.event_overrides
            w.load(0);w.automatic.set(0);w.gear.set(0);w.start_button.invoke();wait_for(lambda:w.host.snapshot().get('lifecycle')==4)
            w.vars['throttle'].set(.95);advance(1.5);w.vars['throttle'].set(0);advance(.7)
            automatic=w.host.snapshot();assert automatic['event_started']>=1 and automatic['event_policy_stats']['bursts_attempted']>=1,automatic
            w.stop();advance(.3);assert not w.last_error,w.last_error
            report.update(ui=True,manual_button=True,old_v18_take_preserved=True,take_replay=replay,
                          automatic_app=automatic,catalog_isolation=True)
        finally:w.stop();advance(.2);root.destroy()
    (args.output/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False),flush=True)


if __name__=='__main__':main()

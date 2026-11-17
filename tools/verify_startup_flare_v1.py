"""Verify production startup selection, lifecycle, stems, replay and actual App.

No research audition Host is used. Output artifacts are write-once per run.
"""
import argparse
import ctypes as C
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import time

from vehicle_controller.native import Bridge,Engine
from vehicle_controller import take,recipe
from vehicle_controller.startup_sound import defaults
from vehicle_scenarios.start_idle import start_idle_lifecycle


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--ui',action='store_true');args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    import sys
    assert 'numpy' not in sys.modules
    import numpy as np
    import soundfile as sf
    repo=Path(__file__).resolve().parents[1];bridge=Bridge(repo)
    old=Bridge(repo,repo/'build-vehicle-source-v14/bin/Release/vsl_source_bridge.dll')
    initial,features=bridge.initial(0);initial=defaults(initial,bridge.event_available_mask,features)
    assert features&128 and initial['startup_gain']==1 and not initial['events']['enabled']
    initial.update(mode=1,ignition=1,start_id=1,gear=0,automatic=0,brake=.65)
    value=take.create(bridge,0,initial);value['frames']=5*48000

    def render(b,doc,chunk=480,capture=True):
        mix=[];stems=[];states=[];index=0;events=[]
        with Engine(b,doc['catalog']['id'],doc['event_overrides'],doc['startup_response'],doc.get('event_policy'),doc.get('dna_bank')) as engine:
            engine.set(doc['initial'])
            while engine.frame<doc['frames']:
                while index<len(doc['events']) and doc['events'][index]['frame']==engine.frame:
                    engine.set(doc['events'][index]['control']);index+=1
                end=min(engine.frame+chunk,doc['frames'],doc['events'][index]['frame'] if index<len(doc['events']) else doc['frames'])
                n=end-engine.frame;mix.append(np.frombuffer(engine.process(n),dtype='<f4').copy().reshape(n,2))
                if capture:stems.append(np.ctypeslib.as_array(engine.stems)[:n*b.channels()].copy().reshape(n,b.channels()))
                states.append(engine.state());events.extend(engine.last_events)
        return np.concatenate(mix),np.concatenate(stems) if capture else None,states,events

    mix,stems,states,events=render(bridge,value)
    other,other_stems,_,_=render(bridge,value,217)
    assert np.array_equal(mix,other) and np.array_equal(stems,other_stems)
    assert np.isfinite(mix).all() and np.max(abs(mix))<.95 and not events
    assert np.max(abs(mix[:2400]))==0
    offsets=np.cumsum([0]+[row['channels'] for row in bridge.stems]);total=np.zeros_like(mix,dtype='float64')
    for k,row in enumerate(bridge.stems):
        part=stems[:,offsets[k]:offsets[k+1]]
        total+=part if row['channels']==2 else np.repeat(part,2,axis=1)*(1 if row['name']=='legacy_event' else 2**-.5)
    stem_error=float(np.max(abs(total-mix)));assert stem_error<1e-7,stem_error
    source=Path('E:/VehicleSoundLab/references/analysis/startup_rotation_v1/listen2')
    selected,rate=sf.read(source/'Candidate.wav',dtype='float32');assert rate==48000
    # First 1.4s has no background contribution in either implementation.
    error=float(np.max(abs(mix[2400:2400+67200]-selected[91680:91680+67200])))
    assert error<2e-7,('selected foreground mismatch',error)
    catch,rate=sf.read(source/'catch.wav',dtype='float32');assert rate==48000
    native=stems[:,offsets[8]:offsets[9]]
    full_error=float(np.max(abs(native[2400:103200]-catch[91680:192480])))
    assert full_error<2e-7,('whole selected catch mismatch',full_error)
    baseline=deepcopy(value);baseline['initial']['startup_gain']=0
    base,base_stems,_,_=render(old,baseline)
    assert np.array_equal(mix[103201:],base[103201:])
    assert np.array_equal(stems[103201:],base_stems[103201:])
    sf.write(args.output/'Startup.wav',mix,48000,subtype='FLOAT')

    # Start, cancel during catch, stop fully, start again in the SAME engine.
    repeated=deepcopy(value);repeated['frames']=6*48000
    c=deepcopy(initial);c['ignition']=0;take.append(repeated,round(.8*48000),c)
    c.update(ignition=1,start_id=2);take.append(repeated,round(1.6*48000),c)
    again,again_stems,again_states,_=render(bridge,repeated)
    check,_,_,_=render(bridge,repeated,217,False);assert np.array_equal(again,check)
    assert np.max(abs(again))<.95 and np.isfinite(again).all()
    assert np.max(abs(again_stems[round(1.7*48000):round(2.7*48000),offsets[8]:offsets[9]]))>.01
    assert again_states[-1]['lifecycle']==4
    sf.write(args.output/'Restart.wav',again,48000,subtype='FLOAT')
    muted=deepcopy(value);muted['initial']['startup_gain']=0
    muted_mix,muted_stems,_,_=render(bridge,muted)
    assert np.max(abs(muted_stems[:,offsets[8]:offsets[9]]))==0
    assert np.max(abs(muted_mix[:69600]))==0
    # Invalid controls must not partially adopt; event overrides cannot re-add
    # the discarded starter on top of the production startup.
    with Engine(bridge,0) as engine:
        original=deepcopy(engine.controls)
        for key,val in [('startup_gain',float('nan')),('startup_gain',3),('catch_gain',1),('legacy_event_gain',1)]:
            bad=deepcopy(original);bad[key]=val
            try:engine.set(bad)
            except ValueError:pass
            else:raise AssertionError(('invalid control accepted',key))
            assert engine.controls==original
    # Normal take/recipe save and replay preserve the new source identity.
    path=args.output/'Startup.vsltake.json';take.save(path,value);loaded=take.read(path,bridge)
    with Engine(bridge,0,startup_response=loaded['startup_response']) as engine:
        engine.set(loaded['initial']);pieces=[];index=0
        while engine.frame<loaded['frames']:
            data,index=take.replay_block(engine,loaded,index,min(480,loaded['frames']-engine.frame));pieces.append(data)
    assert b''.join(pieces)==mix.tobytes()
    preset=recipe.create(bridge,0,initial,'踏板驾驶',{},bridge.startup_defaults)
    preset_path=args.output/'Startup.recipe.json';take.save(preset_path,preset)
    saved_preset=json.loads(preset_path.read_text(encoding='utf-8'))
    recipe.validate(bridge,saved_preset);assert saved_preset['control']['startup_gain']==1
    # Every other catalog retains its previous native controls/sound path.
    catalog_checks=[]
    for selection in range(1,len(bridge.catalog)):
        nc,nf=bridge.initial(selection);oc,of=old.initial(selection)
        assert nc==oc and nf==of and not nf&128
        nc.update(ignition=1,start_id=1)
        new_doc=take.create(bridge,selection,nc,startup_response=old.startup_defaults);new_doc['frames']=4800
        a,_,_,_=render(bridge,new_doc,capture=False);b,_,_,_=render(old,new_doc,capture=False)
        assert np.array_equal(a,b);catalog_checks.append(selection)

    cycle,_=start_idle_lifecycle(bridge,0,initial,{},bridge.startup_defaults)
    cycle_mix,_,cycle_states,_=render(bridge,cycle,capture=False)
    assert max(s['speed_mps'] for s in cycle_states)>5 and cycle_states[-1]['lifecycle']==0
    assert np.isfinite(cycle_mix).all() and np.max(abs(cycle_mix))<.95
    assert np.max(abs(cycle_mix[round(.4*48000):round(1.8*48000)]))>.01
    sf.write(args.output/'Full-cycle.wav',cycle_mix,48000,subtype='FLOAT')
    report=dict(schema='vsl.production-startup-flare/1',bridge_sha256=bridge.sha256,
        prior_bridge_sha256=old.sha256,selected_seconds=[1.91,4.01],foreground_max_error=error,
        whole_catch_stem_max_error=full_error,preparation_silent=True,partition_exact=True,
        stems_max_error=stem_error,late_idle_stems_exact=True,record_replay_exact=True,
        restart_and_cancel=True,other_catalogs_exact=catalog_checks,full_cycle=True,
        peak=float(np.max(abs(mix))),ui=False)
    if args.ui:
        import tkinter as tk
        from vehicle_controller.ui import Window
        from PIL import ImageGrab
        root=tk.Tk();window=Window(root,repo,args.output/'takes');window.muted.set(1)
        def advance(seconds):
            end=time.monotonic()+seconds
            while time.monotonic()<end:root.update();time.sleep(.005)
        try:
            advance(.2);assert 'V17' in root.title()
            assert not hasattr(window,'new_startup_button') and not hasattr(window,'audition_startup')
            assert window.controls()['startup_gain']==1 and not window.startup_sound.scale.instate(['disabled'])
            window.start_button.invoke();advance(4)
            assert window.running() and window.host.snapshot()['lifecycle']==4
            window.stop();advance(.3);assert not window.running(),window.host.snapshot()
            normal=window.host.snapshot();assert not normal.get('error'),normal
            window.save_take();paths=list((args.output/'takes').glob('*.vsltake.json'));assert len(paths)==1
            recorded=take.read(paths[0],bridge);assert recorded['initial']['startup_gain']==1
            window.start(recorded);advance(recorded['frames']/48000+1)
            state=window.host.snapshot();assert not window.running() and not state.get('error'),state
            assert state['frame']==recorded['frames'] and state['underflows']==0,state
            # Invoke the actual complete-flow button; no separate audition Host.
            window.demo_button.invoke();advance(3)
            assert window.running() and window.host.snapshot()['lifecycle']==4
            window.stop();advance(.3);assert not window.running()
            assert not window.last_error,window.last_error
            ImageGrab.grab(window=root.winfo_id()).save(args.output/'App-V17.png')
            assert window.startup_sound.scale.winfo_viewable()
            assert window.footer.winfo_rooty()+window.footer.winfo_height()<=root.winfo_rooty()+root.winfo_height()
            report.update(ui=True,normal_host=normal,replay_host=state,
                normal_button=True,complete_flow_button=True,save_take=True,no_AB=True,footer_visible=True)
        finally:window.stop();advance(.2);root.destroy()
    (args.output/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False),flush=True)


if __name__=='__main__':main()

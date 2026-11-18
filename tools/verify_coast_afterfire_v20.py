"""Paired native-C sound/clock checks and delivery WAVs for App V20."""
import argparse
from copy import deepcopy
import ctypes as C
import hashlib
import json
from pathlib import Path
import numpy as np
import soundfile as sf
from vehicle_controller.native import Bridge,Engine
from vehicle_controller.startup_sound import defaults as startup_defaults
from vehicle_controller.afterfire import defaults as afterfire_defaults
from vehicle_controller import take,recipe
from vehicle_scenarios.start_idle import start_idle_lifecycle

def render(b,doc,chunk=480):
    mix=[];stems=[];states=[];notices=[];index=0
    with Engine(b,0,doc['event_overrides'],doc['startup_response'],doc['event_policy']) as e:
        e.set(doc['initial'])
        while e.frame<doc['frames']:
            while index<len(doc['events']) and doc['events'][index]['frame']==e.frame:
                e.set(doc['events'][index]['control']);index+=1
            n=min(chunk,doc['frames']-e.frame,doc['events'][index]['frame']-e.frame if index<len(doc['events']) else doc['frames'])
            mix.append(np.frombuffer(e.process(n),dtype='<f4').copy().reshape(-1,2))
            stems.append(np.ctypeslib.as_array(e.stems)[:n*b.channels()].copy().reshape(-1,b.channels()))
            states.append(dict(e.state(),begin=e.frame-n));notices.extend(e.last_events)
        stats=e.policy_stats()
    return np.concatenate(mix),np.concatenate(stems),states,notices,stats

def cache_control_edits(new,baseline):
    """Exercise cache invalidation while all fingerprint controls are audible."""
    edits=[('motion',.1),('motion',1.2),('idle_blend',.6),('idle_blend',1.2),
           ('air_continuity',.9),('pitch_follow',.9),('rpm',1800),('rpm',950)]
    captures=[]
    for bridge in (new,baseline):
        ctrl,_=bridge.initial(0)
        ctrl.update(mode=0,ignition=1,start_id=1,rpm=1000,load=0,backfire=0)
        ctrl['events']['enabled']=0
        parts=[];stems=[]
        with Engine(bridge,0) as engine:
            engine.set(ctrl)
            for block in range(540):
                if block>=300 and (block-300)%30==0:
                    key,value=edits[(block-300)//30]
                    if key=='rpm':ctrl[key]=value
                    else:ctrl['dna'][key]=value
                    engine.set(ctrl)
                parts.append(engine.process(480))
                stems.append(bytes(engine.stems)[:480*bridge.channels()*4])
        captures.append((b''.join(parts),b''.join(stems)))
    assert captures[0]==captures[1],'geometry cache invalidation changed dynamic controls'
    return dict(dynamic_control_edits_exact=True,edits=edits,seconds=5.4,
                new_sha256=new.sha256,baseline_sha256=baseline.sha256)

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
    p.add_argument('--candidate-baseline',type=Path);a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=False)
    repo=Path(__file__).resolve().parents[1]
    new=Bridge(repo);old=Bridge(repo,repo/'build-vehicle-source-v16/bin/Release/vsl_source_bridge.dll')
    c,f=new.initial(0);c=startup_defaults(c,new.event_available_mask,f)
    c['events']['enabled']=0;c['backfire']=0
    doc,_=start_idle_lifecycle(new,0,c,{},new.startup_defaults)
    print('Render 36 s continuous lifecycle, new/old',flush=True)
    n,ns,st,_,_=render(new,doc);o,os,ost,_,_=render(old,doc)
    if a.candidate_baseline:
        baseline=Bridge(repo,a.candidate_baseline)
        cm,cs,_,_,_=render(baseline,doc)
        assert np.array_equal(n,cm) and np.array_equal(ns,cs),'geometry cache changed the sound'
        cache_control_edits(new,baseline)
    assert np.array_equal(n[:19*48000],o[:19*48000]),'startup/idle/acceleration changed'
    assert np.array_equal(ns[:19*48000],os[:19*48000])
    for s,t in zip(st,ost):
        for key in ('rpm','speed_mps','load','gear','lifecycle','operating','gain'):
            assert s[key]==t[key],key
    assert np.max(abs(n))<1 and np.isfinite(n).all()
    def db(x):return float(10*np.log10(max(float(np.mean(x.astype(float)**2)),1e-30)))
    windows={}
    for name,lo,hi in [('acceleration',17,18),('coast',20,21),('braking',22,23)]:
        sl=slice(lo*48000,hi*48000)
        windows[name]=dict(old_dbfs=db(o[sl]),new_dbfs=db(n[sl]),
            delta_db=db(n[sl])-db(o[sl]),old_air_dbfs=db(os[sl,4:6]),new_air_dbfs=db(ns[sl,4:6]))
    assert 4<windows['coast']['delta_db']<10,windows
    # Fixed RPM rules out the falling-speed trajectory as the cause.
    fixed={}
    for b in (old,new):
        ctrl=deepcopy(c);ctrl.update(mode=0,rpm=4000,load=.9,ignition=1,start_id=1,gear=0,automatic=0)
        with Engine(b,0) as e:
            out=[]
            for block in range(900):
                if block==500:ctrl['load']=-.2
                e.set(ctrl);pcm=e.process(480)
                if block>=800:out.append(np.frombuffer(pcm,dtype='<f4'))
            fixed['new' if b is new else 'old']=dict(dbfs=db(np.concatenate(out)),rpm=e.state()['rpm'])
    # Save a short direct listening comparison, no independent normalisation.
    for name,audio in [('Previous-coast',o),('Fixed-coast',n)]:
        sf.write(a.output/(name+'.wav'),audio[17*48000:25*48000],48000,subtype='FLOAT')
    ctrl,f=new.initial(0);ctrl=startup_defaults(ctrl,new.event_available_mask,f)
    ctrl,overrides,policy=afterfire_defaults(new,0,ctrl,f)
    # This historical V20 verifier remains bound to the delivered V2 timbre.
    overrides['afterfire']=json.loads((repo/'presets/events/reference_afterfire_G_v2.json').read_text(encoding='utf-8'))
    assert len(overrides['afterfire']['parameters']['modes'])==3
    from event_authoring.export import c_profile
    assert c_profile(overrides['afterfire']['parameters']) in (repo/'presets/events/reference_afterfire_G_v2.h').read_text(encoding='utf-8')
    manual=deepcopy(ctrl);manual.update(mode=1,gear=0,automatic=0,ignition=0,start_id=0)
    manual['events'].update(manual_type=3,manual_sequence=1)
    md=take.create(new,0,manual,overrides,event_policy=policy);md['frames']=2*48000
    m,ms,mst,mn,_=render(new,md)
    starts=[row for row in mn if row['action']==1]
    assert 6<=len(starts)<=10 and np.max(abs(ms[:,:19]))==0
    assert all(row['type']==3 for row in starts) and not [row for row in mn if row['action'] in (3,4)]
    assert max(row['event_active'] for row in mst)<=4 and np.max(abs(m))<1
    sf.write(a.output/'Afterfire-burst.wav',m,48000,subtype='FLOAT')
    m2,s2,_,n2,_=render(new,md,217)
    assert np.array_equal(m,m2) and np.array_equal(ms,s2) and mn==n2
    # Max count is a queue limit, not an expansion of simultaneous voices.
    dense=deepcopy(md);dense['event_policy'].update(afterfire_min_count=12,afterfire_max_count=12,
        afterfire_interval_min_seconds=.02,afterfire_interval_max_seconds=.02,afterfire_repeat_gain=1.3)
    _,_,ds,dn,_=render(new,dense)
    assert max(s['event_peak'] for s in ds)<=4 and max(s['event_overflow'] for s in ds)==0
    # Both a real fast lift and braking use exactly the same native driver.
    driving,_=start_idle_lifecycle(new,0,ctrl,overrides,new.startup_defaults,policy)
    print('Render automatic burst and source isolation',flush=True)
    full,fs,states,notices,stats=render(new,driving)
    disabled=deepcopy(driving);disabled['initial']['backfire']=0
    for row in disabled['events']:row['control']['backfire']=0
    quiet,qs,_,_,_=render(new,disabled)
    assert np.array_equal(fs[:,:19],qs[:,:19]),'event contaminated continuous synthesis'
    automatic=[row for row in notices if row['action']==1]
    assert 6<=len(automatic)<=10 and not any(s['event_overflow'] for s in states)
    assert all(row['type']==3 for row in automatic)
    assert np.max(abs(full))<1
    sf.write(a.output/'Fixed-coast-and-afterfire.wav',full[17*48000:25*48000],48000,subtype='FLOAT')
    driving['source_events']=notices;take.save(a.output/'V20.vsltake.json',driving)
    loaded=take.read(a.output/'V20.vsltake.json',new)
    with Engine(new,0,loaded['event_overrides'],loaded['startup_response'],loaded['event_policy']) as e:
        e.set(loaded['initial']);parts=[];index=0
        while e.frame<loaded['frames']:
            pcm,index=take.replay_block(e,loaded,index,min(313,loaded['frames']-e.frame));parts.append(pcm)
    assert b''.join(parts)==full.tobytes()
    try:take.read(a.output/'V20.vsltake.json',old)
    except ValueError:pass
    else:raise AssertionError('Frozen engine must reject changed identity')
    preset=recipe.create(new,0,ctrl,'踏板驾驶',overrides,event_policy=policy);recipe.validate(new,preset)
    take.save(a.output/'V20.recipe.json',preset)
    # Other catalogues/custom DNA do not inherit this modified-V12 event preset.
    for selection in range(1,len(new.catalog)):
        value,features=new.initial(selection)
        assert not afterfire_defaults(new,selection,value,features)[1]
    report=dict(schema='vsl.coast-afterfire-v20/1',new_sha256=new.sha256,old_sha256=old.sha256,
        startup_idle_acceleration_first_19s_exact=True,driver_and_master_gain_exact=True,
        windows=windows,fixed_rpm=fixed,partition_217_480_exact=True,replay_313_exact=True,
        continuous_19_channels_event_isolation_exact=True,manual_starts=starts,automatic_starts=automatic,
        automatic_stats=stats,burst_peak_voices=max(s['event_peak'] for s in states),
        saturated_peak_voices=max(s['event_peak'] for s in ds),saturated_queue_overflows=max(s['event_overflow'] for s in ds),
        peak=float(np.max(abs(full))),other_catalogue_event_isolation=True,
        timbre_acceptance_pending=True,reference_is_modified_v12_not_v10=True,
        geometry_cache_exact_vs_candidate=bool(a.candidate_baseline))
    (a.output/'verification.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False),flush=True)

if __name__=='__main__':main()

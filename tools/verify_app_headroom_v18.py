"""Verify C headroom, default preservation, mechanical isolation and the real app."""
import argparse
from copy import deepcopy
import ctypes as C
import json
from pathlib import Path
import time
from vehicle_controller.native import Bridge,Engine,pack,unpack
from vehicle_controller import dna_character as dna,startup,event_policy as policy,take,recipe,dna_bank
from vehicle_controller.startup_sound import defaults
from vehicle_scenarios.start_idle import start_idle_lifecycle


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--ui',action='store_true');args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    import numpy as np
    import soundfile as sf
    repo=Path(__file__).resolve().parents[1];b=Bridge(repo)
    old=Bridge(repo,repo/'build-vehicle-source-v15/bin/Release/vsl_source_bridge.dll')
    report=dict(schema='vsl.app-headroom/1',bridge_sha256=b.sha256,prior_bridge_sha256=old.sha256)
    initial,features=b.initial(0);initial=defaults(initial,b.event_available_mask,features)
    assert features&256 and features&512 and initial['startup_gain']==.5
    initial.update(mode=1,ignition=1,start_id=1,gear=0,automatic=0,brake=.65)
    doc=take.create(b,0,initial);doc['frames']=5*48000
    offsets=np.cumsum([0]+[r['channels'] for r in b.stems])

    def render(bridge,value,chunk=480):
        mix=[];stems=[];states=[];index=0
        with Engine(bridge,value['catalog']['id'],value['event_overrides'],value['startup_response'],value['event_policy'],value['dna_bank']) as e:
            e.set(value['initial'])
            while e.frame<value['frames']:
                while index<len(value['events']) and value['events'][index]['frame']==e.frame:
                    e.set(value['events'][index]['control']);index+=1
                end=min(e.frame+chunk,value['frames'],value['events'][index]['frame'] if index<len(value['events']) else value['frames'])
                n=end-e.frame;mix.append(np.frombuffer(e.process(n),dtype='<f4').copy().reshape(n,2))
                stems.append(np.ctypeslib.as_array(e.stems)[:n*b.channels()].copy().reshape(n,b.channels()))
                states.append(e.state())
        return np.concatenate(mix),np.concatenate(stems),states

    def rejected(engine,control):
        previous=deepcopy(engine.controls)
        assert not b.set(engine.handle,C.byref(pack(control)))
        raw=pack(previous);assert b.controls(engine.handle,C.byref(raw)) and unpack(raw)==previous

    mix,stems,states=render(b,doc)
    prior=deepcopy(doc);prior['initial']['startup_gain']=1
    om,os,_=render(old,prior)
    report['default_max_error']=float(np.max(abs(mix-om)))
    report['default_stems_max_error']=float(np.max(abs(stems-os)))
    assert np.array_equal(mix,om) and np.array_equal(stems,os)
    partition,ps,_=render(b,doc,217)
    assert np.array_equal(mix,partition) and np.array_equal(stems,ps)
    total=np.zeros_like(mix,dtype='float64')
    for k,row in enumerate(b.stems):
        x=stems[:,offsets[k]:offsets[k+1]]
        total+=x if row['channels']==2 else np.repeat(x,2,axis=1)*(1 if row['name']=='legacy_event' else 2**-.5)
    report['stem_sum_error']=float(np.max(abs(total-mix)));assert report['stem_sum_error']<1e-7
    report['partition_exact']=True
    sf.write(args.output/'Default-startup.wav',mix,48000,subtype='FLOAT')
    # Volume changes only the selected startup foreground, with 0.5 nominal.
    volume=[];selected=stems[:103200,offsets[8]:offsets[9]]
    for gain in (0.,1.,2.,2.6):
        x=deepcopy(doc);x['initial']['startup_gain']=gain;x['frames']=103200
        m,s,_=render(b,x)
        error=float(np.max(abs(s[:,offsets[8]:offsets[9]]-selected*(2*gain))))
        assert error<2e-7,(gain,error)
        if gain==0:assert not np.any(s[:,offsets[8]:offsets[9]])
        volume.append(dict(gain=gain,max_scaling_error=error,peak=float(np.max(abs(m)))))
    report['startup_volume']=volume
    # The same old mechanical feature, now owned by the DNA path; no NVH stems.
    mechanical=deepcopy(doc);mechanical['initial']['mechanical_gain']=1
    mm,ms,_=render(b,mechanical)
    mechanical['initial']['startup_gain']=1
    oldm,olds,_=render(old,mechanical)
    assert np.array_equal(mm,oldm) and np.array_equal(ms,olds)
    assert np.max(abs(ms[:,offsets[4]:offsets[5]]))>1e-5
    for k in (3,5,6,7):assert not np.any(ms[:,offsets[k]:offsets[k+1]])
    report['mechanical_preserved_and_retired_stems_zero']=True
    # Exercise every current numeric upper bound through C, then render.
    accepted=[]
    with Engine(b,0) as e:
        c=deepcopy(initial);c.update(rpm=4000,mode=0)
        for key in ('gain','detail','low_mix','coherent_low_gain','resonant_gain','mechanical_gain'):
            x=deepcopy(c);x[key]=1.3;e.set(x);e.process(480);accepted.append(key)
            x[key]=1.30001;rejected(e,x)
        x=deepcopy(c)
        for key,label,lo,hi in dna.FIELDS:x['dna'][key]=hi
        x['dna']['line_state']=x['dna']['air_state']=[2.6]*6
        e.set(x)
        for _ in range(20):assert np.isfinite(np.frombuffer(e.process(480),dtype='<f4')).all()
        accepted+=['dna.'+r[0] for r in dna.FIELDS]+['dna.line_state[6]','dna.air_state[6]']
        for key,label,lo,hi in dna.FIELDS:
            bad=deepcopy(c);bad['dna'][key]=hi+1e-5;rejected(e,bad)
        for key in ('line_state','air_state'):
            bad=deepcopy(c);bad['dna'][key][5]=2.60001;rejected(e,bad)
        for key,value in [('throttle',1.001),('brake',1.001),('gear',8),('startup_gain',2.60001)]+[(k,.1) for k in ('intake_gain','air_gain','road_gain','wind_gain')]:
            bad=deepcopy(c);bad[key]=value;rejected(e,bad)
        x=deepcopy(c);x['events'].update(gain=2.6,pitch=2.6,decay=5.2,texture=2.6,levels=[2.6]*7)
        e.set(x);e.process(480);accepted+=['events.'+k for k in ('gain','pitch','decay','texture','levels[7]')]
        for key,hi in [('gain',2.6),('pitch',2.6),('decay',5.2),('texture',2.6)]:
            bad=deepcopy(c);bad['events'][key]=hi+1e-5;rejected(e,bad)
        bad=deepcopy(c);bad['events']['levels'][0]=2.60001;rejected(e,bad)
    # The main startup forbids old crank/catch overlays. Use a historical
    # catalog to exercise the existing event kernel without inventing a sound.
    with Engine(b,1) as e:
        c=deepcopy(e.controls);kind=next(k for k in range(7) if b.event_available_mask&(1<<k))
        c['events'].update(enabled=1,manual_type=kind,manual_sequence=1,gain=2.6,pitch=2.6,decay=5.2,texture=2.6,levels=[2.6]*7)
        e.set(c)
        for _ in range(30):assert np.isfinite(np.frombuffer(e.process(480),dtype='<f4')).all()
        assert e.state()['event_started']>0
    for module,struct,setter,rows in ((startup,startup.Response,b.startup_set,startup.FIELDS),(policy,policy.Policy,b.event_policy_set,policy.FIELDS)):
        v={r[0]:r[3] for r in rows};v=module.validate(v)
        with Engine(b,0) as e:
            assert setter(e.handle,C.byref(struct(**v)));e.set(initial);e.process(480)
        for r in rows:
            bad=deepcopy(v);bad[r[0]]=r[3]+(1 if r[0].endswith('count') else 1e-5)
            with Engine(b,0) as e:assert not setter(e.handle,C.byref(struct(**bad)))
        accepted += [module.__name__+'.'+r[0] for r in rows]
    # Feature-less residual catalog still supports its extended real gain.
    sel=next(k for k in range(len(b.catalog)) if b.initial(k)[1]&1)
    with Engine(b,sel) as e:
        c=deepcopy(e.controls);c.update(residual_gain=1.3,ignition=1,start_id=1);e.set(c);e.process(480)
    report['extended_limits_exercised']=accepted+['residual_gain']
    # Normal take/preset storage and replay carry the actual extended controls.
    saved=deepcopy(doc);saved['initial'].update(startup_gain=2.6,mechanical_gain=1.3)
    saved['initial']['dna']['line']=2.6
    c=deepcopy(saved['initial']);c['dna']['line']=1.3;take.append(saved,150123,c)
    sm,_,_=render(b,saved)
    path=args.output/'Extended.vsltake.json';take.save(path,saved);read=take.read(path,b)
    with Engine(b,0) as e:
        e.set(read['initial']);pieces=[];index=0
        while e.frame<read['frames']:
            data,index=take.replay_block(e,read,index,min(217,read['frames']-e.frame));pieces.append(data)
    assert b''.join(pieces)==sm.tobytes();report['extended_record_replay_exact']=True
    preset=recipe.create(b,0,saved['initial'],'踏板驾驶',{},b.startup_defaults)
    path=args.output/'Extended.recipe.json';take.save(path,preset);recipe.validate(b,json.loads(path.read_text(encoding='utf-8')))
    try:recipe.validate(old,preset)
    except ValueError:pass
    else:raise AssertionError('Frozen library accepted a new-identity preset')
    cycle,_=start_idle_lifecycle(b,0,initial,{},b.startup_defaults)
    cm,cs,ct=render(b,cycle);assert np.isfinite(cm).all() and np.max(abs(cm))<.95 and ct[-1]['lifecycle']==0
    assert max(s['speed_mps'] for s in ct)>5
    report['complete_36s_cycle']=True
    report['ui']=False
    if args.ui:
        import tkinter as tk
        from vehicle_controller.ui import Window,SOLO_INDEX
        from PIL import ImageGrab
        root=tk.Tk();w=Window(root,repo,args.output/'takes');w.muted.set(1)
        def advance(seconds):
            end=time.monotonic()+seconds
            while time.monotonic()<end:root.update();time.sleep(.005)
        def capture(name):
            advance(.2);ImageGrab.grab(window=root.winfo_id()).save(args.output/name)
        def inside(widget):
            node=widget
            while node is not root:
                parent=node.master
                assert node.winfo_rooty()+node.winfo_height()<=parent.winfo_rooty()+parent.winfo_height()+2,(widget,node)
                node=parent
        try:
            advance(.2);assert 'V18' in root.title()
            assert not any(k in w.widgets for k in ('intake_gain','air_gain','road_gain','wind_gain'))
            assert w.controls()['startup_gain']==.5 and float(w.startup_sound.scale.cget('to'))==2.6
            assert SOLO_INDEX['DNA · 机械特征']==4 and SOLO_INDEX['启动声音']==8
            for key in ('gain','detail','low_mix','coherent_low_gain','resonant_gain','mechanical_gain'):
                assert float(w.widgets[key][0].cget('to'))==1.3
            capture('App-V18-driving.png');inside(w.startup_sound.scale);inside(w.footer)
            w.tabs.select(w.dna_page);advance(.2);assert w.widgets['mechanical_gain'][0].winfo_viewable()
            inside(w.widgets['mechanical_gain'][0]);capture('App-V18-DNA.png')
            w.vars['mechanical_gain'].set(1.3);w.vars['startup_gain'].set(2.6)
            w.dna_tone.fields['line'].set(2.6);advance(.1)
            assert w.controls()['dna']['line']==2.6 and w.values['mechanical_gain'][0].get()=='130%'
            w.start_button.invoke();advance(3.2);assert w.running() and not w.host.snapshot().get('error')
            w.stop();advance(.3);normal=w.host.snapshot();assert not w.running() and not normal.get('error'),normal
            w.save_take();paths=list((args.output/'takes').glob('*.vsltake.json'));assert len(paths)==1
            recorded=take.read(paths[0],b);assert recorded['initial']['startup_gain']==2.6
            w.start(recorded);advance(recorded['frames']/48000+.6)
            replay=w.host.snapshot();assert not w.running() and not replay.get('error'),replay
            assert replay['frame']==recorded['frames'] and replay['underflows']==0
            w.vars['startup_gain'].set(.5);w.vars['mechanical_gain'].set(0);w.dna_tone.load(dna.defaults())
            w.tabs.select(w.drive);w.demo_button.invoke();advance(3)
            assert w.running() and w.host.snapshot()['lifecycle']==4
            w.stop();advance(.3);assert not w.last_error,w.last_error
            report.update(ui=True,normal_host=normal,replay_host=replay,mechanical_on_dna_page=True,no_retired_templates=True)
        finally:w.stop();advance(.2);root.destroy()
    (args.output/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False),flush=True)


if __name__=='__main__':main()

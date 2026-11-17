"""Actual App defaults -> existing C events -> measured startup -> idle.

No new timbre fitting or C DSP. Own Tk controls only, no global desktop input.
"""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import time
from unittest.mock import patch
import tkinter as tk
import numpy as np
from PIL import ImageGrab
from scipy.io import wavfile
from vehicle_controller.ui import Window
from vehicle_controller.native import Engine
from vehicle_controller import recipe,take

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    repo=Path(__file__).resolve().parents[1];root=tk.Tk();w=Window(root,repo,a.output/'takes')
    def pump(seconds=.1):
        end=time.monotonic()+seconds
        while time.monotonic()<end:root.update();time.sleep(.005)
    try:
        pump();default=w.controls();assert default['events']['enabled']==1 and default['events']['levels']==[0,1.25,1,0,0,0,0]
        # The compact startup controls edit the very same saved event parameters.
        w.startup_sound.rows[0][1].set(1.4);assert w.controls()['events']['levels'][1]==1.4
        w.vars['event_level_1'].set(1.25)
        export=a.output/'V10-startup-enabled.vslpreset.json'
        with patch('vehicle_controller.ui.filedialog.asksaveasfilename',return_value=str(export)):w.save()
        value=json.loads(export.read_text(encoding='utf-8'));recipe.validate(w.bridge,value)
        w.event_panel.enabled.set(0)
        with patch('vehicle_controller.ui.filedialog.askopenfilename',return_value=str(export)):w.restore()
        assert w.controls()['events']==default['events'],w.message.get()
        # An explicitly disabled saved recipe stays disabled on restoration.
        disabled=deepcopy(value);disabled['control']['events']['enabled']=0;take.save(a.output/'explicit-off.json',disabled)
        with patch('vehicle_controller.ui.filedialog.askopenfilename',return_value=str(a.output/'explicit-off.json')):w.restore()
        assert w.event_panel.enabled.get()==0
        with patch('vehicle_controller.ui.filedialog.askopenfilename',return_value=str(export)):w.restore()
        pump();ImageGrab.grab(window=root.winfo_id()).save(a.output/'app.png')
        for widget in w.startup_sound.inputs:
            assert widget.winfo_ismapped()
            assert widget.winfo_rooty()+widget.winfo_height()<=root.winfo_rooty()+root.winfo_height()
        def plan(control):
            c=deepcopy(control);c.update(ignition=0,start_id=0,gear=0,automatic=0,throttle=0.,brake=.65)
            c['input'].update(source=0,valid=0,sequence=0,speed_mps=0.,acceleration_mps2=0.,tire_slip=0.)
            document=take.create(w.bridge,0,c)
            c=deepcopy(c);c.update(ignition=1,start_id=1);take.append(document,16800,c);document['frames']=4*48000
            return document
        def render(document,chunk=480):
            pcm=[];observations=[];index=0;notices=[];continuous=[]
            with Engine(w.bridge,0) as e:
                e.set(document['initial'])
                while e.frame<document['frames']:
                    data,index=take.replay_block(e,document,index,chunk);pcm.append(data);notices.extend(e.last_events)
                    if chunk==480:
                        # Starts align with this block boundary, so no replay
                        # split can overwrite the corresponding source buffer.
                        continuous.append(np.ctypeslib.as_array(e.stems)[:480*w.bridge.channels()].copy().reshape(480,-1))
                    observations.append(e.state())
            return b''.join(pcm),notices,np.concatenate(continuous) if continuous else None,observations
        doc=plan(default);take.save(a.output/'Startup.vsltake.json',doc);doc=take.read(a.output/'Startup.vsltake.json',w.bridge)
        data,notices,stems,states=render(doc);other,_,_,_=render(doc,217);assert data==other
        old=deepcopy(default);old['events']['enabled']=0;old_data,_,old_stems,_=render(plan(old))
        weak=deepcopy(default);weak['events']['gain']=.5;weak['events']['levels']=[0,1,1,0,0,0,0]
        weak_data,_,_,_=render(plan(weak))
        audio=np.frombuffer(data,'<f4').reshape(-1,2);old_audio=np.frombuffer(old_data,'<f4').reshape(-1,2);weak_audio=np.frombuffer(weak_data,'<f4').reshape(-1,2)
        assert np.isfinite(audio).all() and np.max(abs(audio))<.95
        for name in ('dna','detail','low'):
            k=next(i for i,s in enumerate(w.bridge.stems) if s['name']==name)
            offset=sum(s['channels'] for s in w.bridge.stems[:k]);width=w.bridge.stems[k]['channels']
            assert np.array_equal(stems[:,offset:offset+width],old_stems[:,offset:offset+width]),name
        assert np.array_equal(audio[2*48000:],old_audio[2*48000:])
        def rms(x,start,end):return float(np.sqrt(np.mean(x[round(start*48000):round(end*48000)].astype(float)**2)))
        def db(x):return float(20*np.log10(max(1e-12,x)))
        cr=rms(audio,.38,.60);assert cr>1e-4 and rms(old_audio,.38,.60)==0
        idle=rms(audio,2.,3.5);catch=rms(audio,.65,1.25);startup=rms(audio,.38,1.25)
        assert db(catch/idle)>4,(catch,idle)
        starts=[n for n in notices if n['action']==1];assert [n['type'] for n in starts]==[1,2],starts
        wavfile.write(a.output/'Startup-to-idle.wav',48000,audio)
        wavfile.write(a.output/'Previous-no-start.wav',48000,old_audio)
        w.muted.set(1);w.start();pump(2.5);state=w.host.snapshot()
        assert not state.get('error') and state.get('event_started')==2 and state.get('lifecycle')==4,state
        w.stop();deadline=time.monotonic()+5
        while w.running() and time.monotonic()<deadline:pump(.03)
        assert not w.running()
        result=dict(schema='vsl.startup-enabled-check/1',bridge_sha256=w.bridge.sha256,
            defaults=default['events'],quick_controls=True,preset_roundtrip=True,explicit_off_preserved=True,
            event_starts=starts,crank_rms_dbfs=db(cr),catch_rms_dbfs=db(catch),idle_rms_dbfs=db(idle),
            startup_over_idle_db=db(startup/idle),catch_over_idle_db=db(catch/idle),
            startup_gain_over_weak_db=db(startup/rms(weak_audio,.38,1.25)),peak=float(np.max(abs(audio))),
            continuous_stems_exact=True,idle_pcm_exact=True,replay_exact=True,device=state,
            pcm_sha256=hashlib.sha256(data).hexdigest(),timbre_accepted=False,manual_mouse_verified=False)
        (a.output/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({k:v for k,v in result.items() if k!='device'},ensure_ascii=False))
    finally:
        w.stop()
        if w.host and w.host.thread:w.host.thread.join(timeout=5)
        root.destroy()

if __name__=='__main__':main()

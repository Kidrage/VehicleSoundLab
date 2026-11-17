"""Check the real event DSP, authoring measurements, replay, stems and own UI."""
import argparse
from copy import deepcopy
import ctypes
import hashlib
import json
from pathlib import Path
import subprocess
import shutil
import sys
import time


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--ui',action='store_true');a=parser.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    shutil.copy2(__file__,a.output/'executed_verification.py')
    sys.path.insert(0,'E:/VehicleSoundLab/tools/python_deps')
    import numpy as np
    import soundfile as sf
    from event_authoring.measure import observe
    from event_authoring.model import synth
    from vehicle_controller.native import Bridge,Engine
    from vehicle_controller import take
    from vehicle_controller.render import export
    repo=Path(__file__).resolve().parents[1];bridge=Bridge(repo)
    # Known damped 1 kHz oscillator, independently prescribed amplitude and decay.
    t=np.arange(24000)/48000;rng=np.random.default_rng(8211)
    bg=rng.normal(0,.001,(24000,2));x=.2*np.exp(-t/.12)[:,None]*np.sin(2*np.pi*1000*t)[:,None]+bg
    known,_=observe(x,bg);assert min(abs(hz-1000) for hz in known['modal_peaks_hz'])<24
    band=known['bands'][1];assert band['decay_fitted'] and abs(band['decay_seconds']-.12)<.025,band
    report=dict(schema='vsl.event-system-verification/1',bridge_sha256=bridge.sha256,voices_sha256=bridge.voices_sha256,
        event_bank_sha256=bridge.event_bank_sha256,available_mask=bridge.event_available_mask,native_channels=bridge.channels(),
        known_decay_seconds=band['decay_seconds'],known_modal_peaks=known['modal_peaks_hz'],profiles=[],ui=False)
    for kind,name,frames in [(1,'crank',22560),(2,'catch',38400)]:
        raw=a.output/(name+'.f32');proc=subprocess.run([str(repo/'build-event-synth-v1/bin/Release/event_synth_probe.exe'),str(kind),str(frames),str(raw)],capture_output=True,text=True,check=True)
        (a.output/(name+'_probe.json')).write_text(proc.stdout,encoding='utf-8')
        actual=np.fromfile(raw,dtype='<f4');profile=bridge.event_profiles[name]['parameters']
        expected=synth(profile,seconds=frames/48000).astype(np.float32)
        error=float(np.max(abs(expected.astype(float)-actual)))
        assert len(actual)==frames and error<2e-7,(name,error)
        # Review clips use one fixed quarter gain, before file encoding; no clipping.
        sf.write(a.output/(name+'_c_review.wav'),np.column_stack([actual,actual])*.25,48000,subtype='FLOAT')
        report['profiles'].append(dict(kind=name,frames=frames,independent_python_vs_c_max_error=error,peak=float(np.max(abs(actual)))))
    control,_=bridge.initial(0);control.update(ignition=1,start_id=1)
    control['events']['enabled']=1;control['events']['gain']=.35
    value=take.create(bridge,0,control);record=[];frames=182400
    updates={87137:(2,.9,.8),115200:(1,1.1,1.2)}
    with Engine(bridge,0) as engine:
        engine.set(control)
        while engine.frame<frames:
            if engine.frame in updates:
                kind,pitch,decay=updates[engine.frame]
                control['events'].update(manual_type=kind,manual_sequence=control['events']['manual_sequence']+1,pitch=pitch,decay=decay)
                engine.set(control);take.append(value,engine.frame,control)
            stop=min(engine.frame+480,frames,*[frame for frame in updates if frame>engine.frame])
            record.append(engine.process(stop-engine.frame));value['source_events'].extend(engine.last_events)
        final=engine.state()
    value['frames']=frames;take.save(a.output/'events.vsltake.json',value)
    result=export(bridge,take.read(a.output/'events.vsltake.json',bridge),a.output/'take')
    actual,sr=sf.read(a.output/'take_mix.wav',dtype='float32',always_2d=True)
    direct=np.frombuffer(b''.join(record),dtype=np.float32).reshape(-1,2)
    assert np.array_equal(actual,direct) and result['source_events']==value['source_events']
    sums=np.zeros_like(actual,dtype=np.float64)
    for row in bridge.stems:
        y,rate=sf.read(a.output/('take_'+row['name']+'.wav'),always_2d=True,dtype='float64');assert rate==48000 and len(y)==frames
        if row['channels']==2:sums+=y
        else:sums+=y*(1 if row['name']=='legacy_event' else 2**-.5)
    error=float(np.max(abs(sums-actual)));assert error<2e-6,error
    assert final['event_peak']<=4 and final['event_overflow']==final['event_log_lost']==0,final
    assert any(event['frame']==87137 and event['action']==1 for event in value['source_events'])
    report.update(replay_pcm_exact=True,replay_event_notices_exact=True,non_drive_tick_manual_frame=87137,
        native_reconstruction_max_error=error,final_state=final,source_events=value['source_events'])
    if a.ui:
        import tkinter as tk
        from PIL import ImageGrab
        from vehicle_controller.ui import Window
        root=tk.Tk();window=Window(root,repo,a.output/'ui_takes')
        def advance(seconds):
            end=time.monotonic()+seconds
            while time.monotonic()<end:root.update();time.sleep(.005)
        try:
            advance(.15);assert not window.running() and window.control['events']['enabled']==0
            assert len(window.bridge.stems)==16 and len(window.tabs.tabs())==4
            assert window.event_panel.buttons[3].instate(['disabled'])
            window.muted.set(1);window.tabs.select(window.events_page);window.event_panel.audition(2);advance(.7)
            state=window.host.snapshot();assert not state.get('error') and state['event_started']==1 and state['lifecycle']==0,state
            window.vars['event_pitch'].set(.9);window.vars['event_decay'].set(1.2)
            window.event_panel.audition(1);advance(.7);state=window.host.snapshot()
            assert not state.get('error') and state['event_started']==2,state
            for key in ('legacy_event_gain','startup_gain','catch_gain'):assert window.widgets[key][0].instate(['disabled'])
            captures=[]
            for index,name in enumerate(('drive','tone','events','signals')):
                window.tabs.select(index);advance(.1)
                picture=ImageGrab.grab(window=root.winfo_id());picture.save(a.output/(name+'.png'))
                captures.append(hashlib.sha256((a.output/(name+'.png')).read_bytes()).hexdigest())
            assert len(set(captures))==4
            window.tabs.select(window.events_page);advance(.1)
            for key,(widget,feature) in window.widgets.items():
                if key.startswith('event_'):
                    assert widget.winfo_ismapped() and widget.winfo_rooty()+widget.winfo_height()<root.winfo_rooty()+root.winfo_height(),key
            window.save_take();saved=list((a.output/'ui_takes').glob('*.vsltake.json'));assert saved
            received=take.read(saved[0],window.bridge);assert received['source_events']
            report.update(ui=True,ui_method='Application-owned Tk actions, own-HWND captures, muted WinMM output',
                no_autoplay=True,missing_event_buttons_disabled=True,manual_without_engine_start=True,
                exposed_event_controls=True,legacy_layers_disabled_in_candidate_mode=True,ui_native_stems=16,
                ui_saved_identity_events=True,ui_final_state=state)
        finally:
            window.stop();deadline=time.monotonic()+4
            while window.running() and time.monotonic()<deadline:root.update();time.sleep(.01)
            root.destroy()
    (a.output/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps({key:report[key] for key in ('schema','available_mask','native_channels','replay_pcm_exact','replay_event_notices_exact','native_reconstruction_max_error','ui')},ensure_ascii=False))


if __name__=='__main__':
    try:main()
    except Exception:
        import traceback
        if '--output' in sys.argv:
            folder=Path(sys.argv[sys.argv.index('--output')+1]);folder.mkdir(parents=True,exist_ok=True)
            (folder/'failure.txt').write_text(traceback.format_exc(),encoding='utf-8')
        raise

"""Historical V16 scene check; --ui requires its frozen V16 UI sources.

The current production App is checked by verify_startup_flare_v1.py.
"""
import argparse,ctypes as C,hashlib,json,time
from pathlib import Path
from vehicle_controller.native import Bridge,Engine
from startup_character_v1.archived_audition import Scene

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--ui',action='store_true');a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    import sys
    assert 'numpy' not in sys.modules,'App scene must not import NumPy'
    import numpy as np
    import soundfile as sf
    repo=Path(__file__).resolve().parents[1];bridge=Bridge(repo,repo/'build-vehicle-source-v14/bin/Release/vsl_source_bridge.dll');reference=Path('E:/VehicleSoundLab/references/analysis/startup_rotation_v1/listen2')
    results={}
    def render(previous,chunk):
        with Scene(repo,previous) as scene,Engine(bridge,0,startup_response=scene.response) as engine:
            output=[];parts=[]
            while engine.frame<scene.frames:
                scene.adopt(engine);n=min(chunk,240-engine.frame%240,scene.frames-engine.frame);engine.process(n)
                output.append(np.frombuffer(scene.process(engine.mix,n),dtype='<f4').copy().reshape(-1,2))
                parts.append(np.ctypeslib.as_array(scene.parts)[:n*8].copy().reshape(n,8))
            return np.concatenate(output),np.concatenate(parts)
    for previous,name in ((False,'new'),(True,'previous')):
        mix,parts=render(previous,480);other,_=render(previous,217)
        assert np.array_equal(mix,other)
        saved,rate=sf.read(reference/('Previous-V3.wav' if previous else 'Candidate.wav'),dtype='float32');assert rate==48000
        error=float(np.max(abs(mix-saved)));assert error<2e-6,(name,error)
        combined=np.zeros_like(mix)
        for k in range(4):combined+=parts[:,2*k:2*k+2]
        assert np.array_equal(mix,combined) and np.isfinite(mix).all() and np.max(abs(mix))<.95
        sf.write(a.output/(name+'.wav'),mix,48000,subtype='FLOAT');np.savez(a.output/(name+'-stems.npz'),stems=parts)
        results[name]=dict(reference_max_error=error,partition_exact=True,stems_recombine_exact=True,peak=float(np.max(abs(mix))))
    new,_=sf.read(a.output/'new.wav',dtype='float32');old,_=sf.read(a.output/'previous.wav',dtype='float32')
    assert np.array_equal(new[round(1.91*48000):],old[round(1.91*48000):])
    # Reject invalid native timeline before altering voices/output or the clock.
    with Scene(repo) as scene:
        scene.timeline.handoff=0;base=(C.c_float*480)()
        try:scene.process(base,240)
        except RuntimeError:pass
        else:raise AssertionError('Invalid native timeline accepted')
        assert scene.frame==0
    report=dict(schema='vsl.startup-app-audition/1',bridge_sha256=bridge.sha256,cases=results,other_actions_identical=True,no_numpy_in_app=True,native_bad_timeline_rejected=True,ui=False)
    if a.ui:
        import tkinter as tk
        from vehicle_controller.ui import Window
        from PIL import ImageGrab
        root=tk.Tk();window=Window(root,repo,a.output/'takes');window.muted.set(1)
        def advance(seconds):
            end=time.monotonic()+seconds
            while time.monotonic()<end:root.update();time.sleep(.005)
        try:
            root.update();assert 'V16' in root.title();assert not window.running()
            reports=[]
            for previous,button in ((False,window.new_startup_button),(True,window.old_startup_button)):
                button.invoke();advance(.3);assert window.running()
                window.save_take();assert '试听' in window.message.get() and not list((a.output/'takes').glob('*.json'))
                assert window.dna_solo_box.instate(['disabled'])
                deadline=time.monotonic()+12
                while window.running() and time.monotonic()<deadline:advance(.05)
                state=window.host.snapshot();assert not window.running() and not state.get('error'),state
                assert state['frame']==336000 and state['underflows']==0,state
                reports.append(dict(previous=previous,state=state))
                advance(.1);assert not window.new_startup_button.instate(['disabled'])
            window.new_startup_button.invoke();advance(.25);window.stop();advance(.3);assert not window.running()
            window.solo.set('完整干声');advance(.1)
            picture=ImageGrab.grab(window=root.winfo_id());picture.save(a.output/'app-v16.png')
            for button in (window.new_startup_button,window.old_startup_button):
                parent=button.master
                while parent is not None:
                    assert button.winfo_rooty()+button.winfo_height()<=parent.winfo_rooty()+parent.winfo_height(),('clipped',str(button),str(parent))
                    parent=parent.master
            report.update(ui=True,muted_real_WinMM=reports,early_stop_passed=True,fake_take_refused=True,buttons_visible=True)
        finally:
            window.stop();advance(.2);root.destroy()
    (a.output/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(ui=report['ui'],cases=results,other_actions_identical=True),ensure_ascii=False),flush=True)
if __name__=='__main__':main()

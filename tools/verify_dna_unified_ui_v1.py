"""Bounded checks of this app's own Tk controls, without global desktop input."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import time
from unittest.mock import patch
import tkinter as tk
from PIL import ImageGrab
from vehicle_controller.ui import Window

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    root=tk.Tk();w=Window(root,Path(__file__).resolve().parents[1],a.output/'takes')
    def pump(seconds=.1):
        end=time.monotonic()+seconds
        while time.monotonic()<end:root.update();time.sleep(.005)
    try:
        pump();assert not w.running();w.tabs.select(w.dna_page);pump()
        w.dna_tone.fields['line'].set(.82);w.dna_tone.fields['air'].set(1.17)
        w.dna_tone.fields['line_state'][2].set(.9);w.dna_tone.fields['air_state'][5].set(1.2)
        expected=deepcopy(w.controls()['dna']);assert expected['line']==.82 and expected['air']==1.17
        path=a.output/'UI-recipe.json'
        with patch('vehicle_controller.ui.filedialog.asksaveasfilename',return_value=str(path)):w.save()
        assert path.is_file() and json.loads(path.read_text(encoding='utf-8'))['control']['dna']==expected
        w.dna_tone.fields['line'].set(.1)
        with patch('vehicle_controller.ui.filedialog.askopenfilename',return_value=str(path)):w.restore()
        assert w.controls()['dna']==expected,w.message.get()
        pump();ImageGrab.grab(window=root.winfo_id()).save(a.output/'dna.png')
        clipped=[]
        for widget in w.dna_tone.inputs:
            if widget.winfo_ismapped() and (widget.winfo_rootx()+widget.winfo_width()>root.winfo_rootx()+root.winfo_width() or
                 widget.winfo_rooty()+widget.winfo_height()>root.winfo_rooty()+root.winfo_height()):clipped.append(str(widget))
        assert not clipped,clipped
        w.tabs.select(w.tone);pump();ImageGrab.grab(window=root.winfo_id()).save(a.output/'layers.png')
        w.tabs.select(w.drive);w.muted.set(1);w.start();pump(2.5)
        state=w.host.snapshot();assert not state.get('error'),state
        assert state.get('frame',0)>48000 and state.get('lifecycle')==4,state
        ImageGrab.grab(window=root.winfo_id()).save(a.output/'driving.png')
        w.stop();deadline=time.monotonic()+5
        while w.running() and time.monotonic()<deadline:pump(.03)
        assert not w.running();report=dict(schema='vsl.unified-dna-ui-check/1',checks=['own-controls','preset-save-load','six-state-fields','layout-bounds','muted-device-start-stop'],manual_mouse_verified=False,state=state)
        (a.output/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(report,ensure_ascii=False))
    finally:
        w.stop()
        if w.host and w.host.thread:w.host.thread.join(timeout=5)
        root.destroy()

if __name__=='__main__':main()

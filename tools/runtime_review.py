"""Shared render/audition/device verification for versioned local reviews."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/python_deps'))
import numpy as np
import soundfile as sf
from PIL import Image
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def rms(x):return float(10*np.log10(max(float(np.mean(x*x)),1e-30)))
def render(exe,path,args,version,extra=()):
    command=[str(exe),str(path),*args,*extra]
    done=subprocess.run(command,check=True,capture_output=True,text=True,timeout=120)
    assert f'DSP {version}' in done.stdout
    x,sr=sf.read(path,always_2d=True)
    assert sr==48000 and np.isfinite(x).all() and np.max(abs(x))<.95
    return x,dict(command=command,sha256=sha(path),frames=len(x),channels=x.shape[1],rms_dbfs=rms(x),peak=float(np.max(abs(x))))
def audition(out,arrays,versions,name):
    gains=[10**((-23-rms(x))/20) for x in arrays]
    common=min(1,.85/max(float(abs(x).max())*g for x,g in zip(arrays,gains)))
    result={}
    for version,x,g in zip(versions,arrays,gains):
        target=out/f'audition_{name}_{version}.wav';sf.write(target,x*g*common,48000,subtype='PCM_24')
        result[version]=dict(file=target.name,sha256=sha(target),gain_db=float(20*np.log10(g*common)),
            processing='Explicit full-clip stereo unweighted RMS match to -23 dBFS and common pair peak trim. Not LUFS.')
    return result
def smoke(build,out,version):
    startup=subprocess.STARTUPINFO();startup.dwFlags|=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=0
    subprocess.run([str(build/'Release/VehicleSoundLab.exe'),'--smoke-test'],cwd=ROOT,startupinfo=startup,check=True,timeout=45)
    for name in ['ui_smoke.json','ui_smoke.ini','ui_smoke.wav']:shutil.copy2(ROOT/'renders'/name,out/name)
    for name in ['ui_ready','ui_listening','ui_detail']:
        with Image.open(ROOT/f'renders/{name}.bmp') as image:image.save(out/f'{name}.png')
    data=json.loads((out/'ui_smoke.json').read_text())
    assert data['dsp']==version and data['device_stream_muted']
    for key in ['waveOut_opened_and_queued_audio','export_succeeded','running_latch','manual_shift','shutdown_to_off']:assert data[key],key
    assert data['queue_empty_observations']==0
    assert .95<data['device_seconds']/data['wall_seconds']<1.02
    assert data['render_ms_mean']<data['block_frames']/48
    return data
def scene_paths(scene,out):
    meta=json.loads(scene.read_text())
    for obj in meta['objects']:
        file=Path(obj['file']);obj['sha256']=sha(file);obj['file']=str(file.relative_to(out)).replace('\\','/')
    scene.write_text(json.dumps(meta,indent=2))

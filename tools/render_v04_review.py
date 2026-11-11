"""Render V0.4 against frozen V0.3, then measure the actual device budget."""
from pathlib import Path
import csv
import hashlib
import json
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/python_deps'))
import numpy as np
import soundfile as sf
from scipy import signal
from PIL import Image

OUT=ROOT/'renders/v0.4.0'
NEW=ROOT/'build-v04/Release/vsl_render.exe'
OLD=ROOT/'baselines/v0.3.0/bin/vsl_render.exe'
CASES={
    'drive':['--seconds','30','--width','.8'],
    'lift':['--seconds','7.5','--scenario','lift','--width','.8'],
    'shifts':['--seconds','13','--scenario','shifts','--width','.8'],
    '850':['--seconds','6','--rpm','850','--load','.18','--width','.8'],
    '2500':['--seconds','6','--rpm','2500','--load','.85','--width','.8'],
    '5000':['--seconds','6','--rpm','5000','--load','.85','--width','.8'],
    '8000':['--seconds','6','--rpm','8000','--load','.85','--width','.8'],
    'pure5000':['--seconds','6','--rpm','5000','--load','.85','--width','.8','--pure']}
BANDS=[(28,120),(120,400),(400,1200),(1200,3000),(3000,8000),(8000,14000)]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
rms=lambda x:float(10*np.log10(max(float(np.mean(x*x)),1e-30)))


def render(exe,path,args,version,extra=()):
    command=[str(exe),str(path),*args,*extra]
    result=subprocess.run(command,check=True,capture_output=True,text=True,timeout=120)
    assert f'DSP {version}' in result.stdout
    x,sr=sf.read(path,always_2d=True)
    assert sr==48000 and np.isfinite(x).all() and np.max(abs(x))<.95
    return x,dict(command=command,sha256=sha(path),frames=len(x),channels=x.shape[1],rms_dbfs=rms(x),peak=float(np.max(abs(x))))


def spectrum(x):
    f,p=signal.welch(x[3*48000:-1200],48000,nperseg=8192,axis=0,detrend=False)
    p=p.mean(axis=1)
    return [dict(hz=[lo,hi],power=float(p[(f>=lo)&(f<hi)].sum()*48000/8192)) for lo,hi in BANDS]


def smoke():
    startup=subprocess.STARTUPINFO()
    startup.dwFlags|=subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow=0
    subprocess.run([str(ROOT/'build-v04/Release/VehicleSoundLab.exe'),'--smoke-test'],
        cwd=ROOT,startupinfo=startup,check=True,timeout=45)
    for name in ['ui_smoke.json','ui_smoke.ini','ui_smoke.wav']:
        shutil.copy2(ROOT/'renders'/name,OUT/name)
    for name in ['ui_ready','ui_listening','ui_detail']:
        with Image.open(ROOT/f'renders/{name}.bmp') as image:
            image.save(OUT/f'{name}.png')
    data=json.loads((OUT/'ui_smoke.json').read_text())
    assert data['dsp']=='0.4.0' and data['device_stream_muted']
    for key in ['waveOut_opened_and_queued_audio','export_succeeded','running_latch','manual_shift','shutdown_to_off']:
        assert data[key],key
    assert data['queue_empty_observations']==0
    assert .95<data['device_seconds']/data['wall_seconds']<1.02
    assert data['render_ms_mean']<data['block_frames']/48
    return data


def main():
    OUT.mkdir(exist_ok=True)
    (OUT/'stems').mkdir(exist_ok=True)
    report=dict(version='0.4.0',seed=48271,comparison_runtime='frozen 0.3.0',cases={})
    for name,args in CASES.items():
        arrays=[];takes={}
        for version,exe in [('v03',OLD),('v04',NEW)]:
            path=OUT/f'{name}_{version}.wav'
            trace=OUT/f'{name}_{version}.csv'
            x,info=render(exe,path,args,'0.3.0' if version=='v03' else '0.4.0',['--trace',str(trace)])
            arrays.append(x);takes[version]=info
        # Sound changes may not feed back into the integrated vehicle clock.
        assert (OUT/f'{name}_v03.csv').read_bytes()==(OUT/f'{name}_v04.csv').read_bytes(),name
        gains=[10**((-23-rms(x))/20) for x in arrays]
        common=min(1,.85/max(float(abs(x).max())*g for x,g in zip(arrays,gains)))
        for version,x,gain in zip(['v03','v04'],arrays,gains):
            target=OUT/f'audition_{name}_{version}.wav'
            sf.write(target,x*gain*common,48000,subtype='PCM_24')
            takes[version]['audition']=dict(file=target.name,sha256=sha(target),gain_db=float(20*np.log10(gain*common)),
                processing='Full-clip stereo unweighted RMS matched to -23dBFS then one common peak trim for the pair. Not LUFS.')
        if name in ['850','2500','5000','8000','pure5000']:
            a,b=map(spectrum,arrays)
            for before,after in zip(a,b):after['new_minus_old_db']=float(10*np.log10(max(after['power'],1e-30)/max(before['power'],1e-30)))
            takes['spectrum']=dict(window_file_seconds=[3,5.975],old=a,new=b,
                limits='Procedural output spectrum. No RPM-aligned reference or perceptual score is implied.')
        report['cases'][name]=takes
        print(name,'vehicle trace identical, PCM24 comparison written',flush=True)
    # Refactoring the non-V10 fallback must preserve its rendered behaviour.
    compatibility={}
    for profile in [1,2,3,4]:
        paths=[]
        for version,exe in [('v03',OLD),('v04',NEW)]:
            path=OUT/f'compat_profile{profile}_{version}.wav'
            render(exe,path,['--profile',str(profile),'--rpm','4000','--load','.65','--seconds','3'],
                   '0.3.0' if version=='v03' else '0.4.0')
            paths.append(path)
        assert paths[0].read_bytes()==paths[1].read_bytes(),profile
        compatibility[str(profile)]=dict(bit_identical=True,sha256=sha(paths[0]))
    report['other_templates']=compatibility
    wave=OUT/'drive_714_v04.wav'
    scene=OUT/'drive_714_scene.json'
    _,report['bed714']=render(NEW,wave,['--seconds','30','--width','.8','--channels','12'],'0.4.0',
        ['--stems',str(OUT/'stems/drive_714'),'--scene',str(scene)])
    metadata=json.loads(scene.read_text(encoding='utf-8'))
    for obj in metadata['objects']:
        file=Path(obj['file']);obj['sha256']=sha(file);obj['file']=str(file.relative_to(OUT)).replace('\\','/')
    scene.write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    assert sf.info(wave).channels==12 and sf.info(wave).subtype=='FLOAT'
    shutil.copy2(ROOT/'renders/v04_ctest_initial.xml',OUT/'ctest.xml')
    report['device']=smoke()
    report['limits']=['Runtime high-order parameters are engineering values, not measured Lamborghini maps.',
        'Listening acceptance, precise video-state/RPM/load calibration, physical NVH/acoustics and 7.1.4 array audition remain open.',
        'The multi-resolution offline fits are not used as stored trajectories or samples inside the C runtime.']
    report['files']={str(p.relative_to(OUT)).replace('\\','/'):sha(p) for p in sorted(OUT.rglob('*'))
        if p.is_file() and p.name!='verification.json'}
    (OUT/'verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report['device'],indent=2),flush=True)


if __name__=='__main__':
    main()

"""Actual V0.5 renders, clock isolation evidence and muted audio-device budget."""
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
from PIL import Image
OUT=ROOT/'renders/v0.5.0'
NEW=ROOT/'build-v05/Release/vsl_render.exe'
OLD=ROOT/'baselines/v0.4.0/bin/vsl_render.exe'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
rms=lambda x:float(10*np.log10(max(float(np.mean(x*x)),1e-30)))
CASES={
    'drive':['--seconds','30','--width','.8'],
    'shifts':['--seconds','13','--scenario','shifts','--width','.8'],
    'neutral':['--seconds','8','--scenario','neutral','--width','.8'],
    'lift':['--seconds','7.5','--scenario','lift','--width','.8'],
    'steady5000':['--seconds','6','--rpm','5000','--load','.85','--width','.8'],
    'custom_dna':['--seconds','6','--rpm','5000','--load','.7','--width','.8']}

def render(exe,path,args,version,extra=()):
    command=[str(exe),str(path),*args,*extra]
    done=subprocess.run(command,check=True,capture_output=True,text=True,timeout=120)
    assert f'DSP {version}' in done.stdout
    x,sr=sf.read(path,always_2d=True)
    assert sr==48000 and np.isfinite(x).all() and np.max(abs(x))<.95
    return x,dict(command=command,sha256=sha(path),frames=len(x),channels=x.shape[1],rms_dbfs=rms(x),peak=float(np.max(abs(x))))

def audition(arrays,versions,name):
    gains=[10**((-23-rms(x))/20) for x in arrays]
    common=min(1,.85/max(float(abs(x).max())*g for x,g in zip(arrays,gains)))
    result={}
    for version,x,g in zip(versions,arrays,gains):
        target=OUT/f'audition_{name}_{version}.wav'
        sf.write(target,x*g*common,48000,subtype='PCM_24')
        result[version]=dict(file=target.name,sha256=sha(target),gain_db=float(20*np.log10(g*common)),
            processing='Explicit full-clip stereo unweighted RMS match to -23 dBFS, common peak trim within pair. Not LUFS.')
    return result

def summarize_trace(file):
    with file.open() as f:rows=list(csv.DictReader(f))
    blips=[r for r in rows if float(r['blip'])>0]
    entries=[r for i,r in enumerate(rows) if r['shift_stage']=='ENGAGE' and (not i or rows[i-1]['shift_stage']!='ENGAGE')]
    for r in blips:
        assert float(r['clutch_transfer'])==0 and int(r['shift_direction'])==-1
        assert float(r['engine_throttle'])>=float(r['blip'])-.00001
    assert all(abs(float(r['shift_error']))<=80.001 for r in entries)
    assert max(int(r['aborted_shifts']) for r in rows)==0
    return dict(rows=len(rows),recorded_blip_frames=len(blips),
        max_blip=max([float(r['blip']) for r in blips] or [0]),
        matched_engagements=len(entries),max_engage_error_rpm=max([abs(float(r['shift_error'])) for r in entries] or [0]),
        blip_with_closed_driver_pedal=sum(float(r['throttle'])<.001 for r in blips),
        max_overrun_events=max(int(r['overruns']) for r in rows),
        limits='Trace sampling is dense during shifts. Exact guards and closed-pedal motion are additionally tested at every 200 Hz control step in CTest.')

def smoke():
    startup=subprocess.STARTUPINFO();startup.dwFlags|=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=0
    subprocess.run([str(ROOT/'build-v05/Release/VehicleSoundLab.exe'),'--smoke-test'],
        cwd=ROOT,startupinfo=startup,check=True,timeout=45)
    for name in ['ui_smoke.json','ui_smoke.ini','ui_smoke.wav']:shutil.copy2(ROOT/'renders'/name,OUT/name)
    for name in ['ui_ready','ui_listening','ui_detail']:
        with Image.open(ROOT/f'renders/{name}.bmp') as image:image.save(OUT/f'{name}.png')
    data=json.loads((OUT/'ui_smoke.json').read_text())
    assert data['dsp']=='0.5.0' and data['device_stream_muted']
    for key in ['waveOut_opened_and_queued_audio','export_succeeded','running_latch','manual_shift','shutdown_to_off']:assert data[key],key
    assert data['queue_empty_observations']==0
    assert .95<data['device_seconds']/data['wall_seconds']<1.02
    assert data['render_ms_mean']<data['block_frames']/48
    return data

def main():
    OUT.mkdir(exist_ok=True);(OUT/'stems').mkdir(exist_ok=True)
    dna=OUT/'engineering_110Hz.dna';dna.write_text('VSL_DNA 1 110 4\n1 0\n0.35 0.3\n0.15 -0.7\n0.06 0.5\n')
    report=dict(version='0.5.0',seed=48271,comparison_runtime='frozen 0.4.0',cases={})
    for name,args in CASES.items():
        arrays=[];takes={}
        for version,exe in [('v04',OLD),('v05',NEW)]:
            extra=['--trace',str(OUT/f'{name}_{version}.csv')]
            if name=='custom_dna':extra+=['--dna',str(dna)]
            x,info=render(exe,OUT/f'{name}_{version}.wav',args,'0.4.0' if version=='v04' else '0.5.0',extra)
            arrays.append(x);takes[version]=info
        audible=audition(arrays,['v04','v05'],name)
        for version in audible:takes[version]['audition']=audible[version]
        if name=='steady5000':assert np.array_equal(*arrays)
        takes['audio_bit_identical']=bool(np.array_equal(*arrays))
        takes['trace']=summarize_trace(OUT/f'{name}_v05.csv')
        report['cases'][name]=takes
        print(name,'rendered and checked',flush=True)
    compatibility={}
    for profile in range(5):
        paths=[]
        for version,exe in [('v04',OLD),('v05',NEW)]:
            path=OUT/f'compat_profile{profile}_{version}.wav'
            render(exe,path,['--profile',str(profile),'--rpm','4000','--load','.65','--seconds','3'],
                   '0.4.0' if version=='v04' else '0.5.0');paths.append(path)
        assert paths[0].read_bytes()==paths[1].read_bytes(),profile
        compatibility[str(profile)]=dict(bit_identical=True,sha256=sha(paths[0]))
    report['factory_steady_compatibility']=compatibility
    args=['--scenario','downshift','--seconds','18','--width','.8']
    x,info=render(NEW,OUT/'downshift_v05.wav',args,'0.5.0',
        ['--trace',str(OUT/'downshift_v05.csv'),'--stems',str(OUT/'stems/downshift')])
    info['audition']=audition([x],['v05'],'downshift')['v05']
    info['trace']=summarize_trace(OUT/'downshift_v05.csv')
    assert info['trace']['blip_with_closed_driver_pedal']>0 and info['trace']['matched_engagements']>=6
    report['downshift']=info
    _,report['bed714']=render(NEW,OUT/'drive_714_v05.wav',['--seconds','30','--width','.8','--channels','12'],'0.5.0',
        ['--stems',str(OUT/'stems/drive_714'),'--scene',str(OUT/'drive_714_scene.json')])
    scene=OUT/'drive_714_scene.json';meta=json.loads(scene.read_text())
    for obj in meta['objects']:
        file=Path(obj['file']);obj['sha256']=sha(file);obj['file']=str(file.relative_to(OUT)).replace('\\','/')
    scene.write_text(json.dumps(meta,indent=2))
    subprocess.run(['ctest','--test-dir',str(ROOT/'build-v05'),'-C','Release','--output-on-failure','--output-junit',str(OUT/'ctest.xml')],check=True)
    subprocess.run([sys.executable,str(ROOT/'tools/check_dna_pipeline.py'),'--renderer',str(NEW),'--out',str(OUT/'dna_check')],check=True)
    report['device']=smoke()
    report['limits']=['Engineering rev actuator and clutch timing, not measured Lamborghini torque/inertia or DCT maps.',
        'Changed driving trajectories mean version switching does not align individual shift events.',
        'Independent clocks deliberately change custom-DNA blends; steady factory templates remain identical.',
        'Muted device smoke and numeric tests do not establish subjective naturalness or 7.1.4 array acceptance.']
    report['files']={str(p.relative_to(OUT)).replace('\\','/'):sha(p) for p in sorted(OUT.rglob('*'))
        if p.is_file() and p.name!='verification.json'}
    (OUT/'verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(dict(device=report['device'],downshift=report['downshift']['trace']),indent=2),flush=True)

if __name__=='__main__':main()

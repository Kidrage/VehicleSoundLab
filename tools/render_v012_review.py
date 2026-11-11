"""Longitudinal driving review. Frozen V011 audio engine vs new drive inputs.

Output is version specific; refuse to overwrite a finalized review.
"""
import csv
import json
import shutil
from runtime_review import ROOT, render, sha, smoke, scene_paths
from review_pairs import common_pair
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

OUT=ROOT/'renders/v0.12.0'
OLD=ROOT/'baselines/v0.11.0/bin/vsl_render.exe'
NEW=ROOT/'build-v012/Release/vsl_render.exe'
CASES={
    'drive':['--scenario','auto','--seconds','30','--width','.8'],
    'downshift':['--scenario','downshift','--seconds','18','--width','.8'],
    'shifts':['--scenario','shifts','--seconds','13','--width','.8'],
    'neutral':['--scenario','neutral','--seconds','8','--width','.8']}


def trace(path):
    return list(csv.DictReader(path.open(encoding='utf-8')))


def metrics(rows):
    return dict(max_speed_kph=max(float(r['speed_kph']) for r in rows),
        last_speed_kph=float(rows[-1]['speed_kph']),last_rpm=float(rows[-1]['rpm']),
        shift_events=int(rows[-1]['shifts']),overrun_events=int(rows[-1]['overruns']),
        aborted_shifts=int(rows[-1]['aborted_shifts']),
        states=sorted(set(r['operating'] for r in rows)))


def plot():
    old=trace(OUT/'drive_v011.csv');new=trace(OUT/'drive_v012.csv')
    fig,axes=plt.subplots(5,1,figsize=(11,11),sharex=True)
    for tag,rows,style in [('V011',old,'--'),('V012',new,'-')]:
        t=[float(r['seconds']) for r in rows]
        for axis,key,label in zip(axes[:3],['rpm','speed_kph','gear'],['RPM','Speed (km/h)','Gear']):
            axis.plot(t,[float(r[key]) for r in rows],style,label=tag,lw=1.5);axis.set_ylabel(label)
    t=[float(r['seconds']) for r in new]
    for key,label in [('wheel_force_n','Wheel'),('service_brake_n','Service brake'),('aerodynamic_n','Aerodynamic'),('rolling_n','Rolling')]:
        axes[3].plot(t,[float(r[key]) for r in new],label=label,lw=1.1)
    axes[3].set_ylabel('Force (N)')
    for key,label in [('throttle','Driver pedal'),('brake','Brake'),('load','Signed torque fraction')]:
        axes[4].plot(t,[float(r[key]) for r in new],label=label,lw=1.2)
    axes[4].set_ylabel('Control');axes[4].set_xlabel('Export time (s)')
    for axis in axes:
        axis.grid(alpha=.2);axis.legend(loc='upper right',fontsize=8,ncol=4)
    fig.suptitle('Identical pedal scenario; changed longitudinal model. Not vehicle telemetry.')
    fig.tight_layout();fig.savefig(OUT/'driving_forces.png',dpi=140);plt.close(fig)


def main():
    if (OUT/'verification.json').exists():raise SystemExit('Final review already exists; preserve it.')
    OUT.mkdir(parents=True,exist_ok=True);(OUT/'stems').mkdir(exist_ok=True)
    result=dict(version='0.12.0',seed=48271,cases={},bench_unchanged={})
    for name,args in CASES.items():
        arrays=[];takes={}
        for tag,exe,ver in [('v011',OLD,'0.11.0'),('v012',NEW,'0.12.0')]:
            extra=['--trace',str(OUT/f'{name}_{tag}.csv')]
            if name=='drive':extra+=['--stems',str(OUT/f'stems/drive_{tag}')]
            x,info=render(exe,OUT/f'{name}_{tag}.wav',args,ver,extra)
            info['driving']=metrics(trace(OUT/f'{name}_{tag}.csv'));arrays.append(x);takes[tag]=info
        auditions=common_pair(OUT,arrays,['v011','v012'],name)
        for tag in takes:takes[tag]['audition']=auditions[tag]
        result['cases'][name]=takes;print(name,json.dumps({tag:takes[tag]['driving'] for tag in takes}),flush=True)
    # Same-state DSP must be preserved, including signed load and imported DNA.
    for name,args in {
        'low':['--rpm','1200','--load','.18','--seconds','4.2'],
        'high':['--rpm','8000','--load','.85','--seconds','4.2'],
        'lift':['--scenario','lift','--seconds','7.5'],
        'imported':['--rpm','4000','--load','.65','--seconds','4.2','--dna',str(ROOT/'renders/v0.9.0/dna_check/known_steady_harmonics.dna')]}.items():
        files=[]
        for tag,exe,ver in [('v011',OLD,'0.11.0'),('v012',NEW,'0.12.0')]:
            path=OUT/f'bench_{name}_{tag}.wav';render(exe,path,args,ver);files.append(path)
        assert files[0].read_bytes()==files[1].read_bytes(),name
        result['bench_unchanged'][name]=sha(files[1]);print('unchanged bench',name,flush=True)
    _,result['bed714']=render(NEW,OUT/'drive_714.wav',CASES['drive']+['--channels','12'],'0.12.0',
        ['--stems',str(OUT/'stems/drive_714'),'--scene',str(OUT/'drive_714_scene.json')])
    scene_paths(OUT/'drive_714_scene.json',OUT)
    for obj in json.loads((OUT/'drive_714_scene.json').read_text())['objects']:
        assert (OUT/obj['file']).read_bytes()==(OUT/f'stems/drive_v012_{obj["name"]}.wav').read_bytes()
    result['stereo_714_identical_sources']=10
    result['device']=smoke(ROOT/'build-v012',OUT,'0.12.0');assert result['device']['longitudinal_model_active']
    for name in ['ui_control_roundtrip.ini','ui_legacy_preset.ini','ui_v08_preset.ini']:
        shutil.copy2(ROOT/'renders'/name,OUT/name)
    shutil.copy2(ROOT/'build-v012/Testing/Temporary/LastTest.log',OUT/'ctest.log')
    assert (OUT/'ctest.log').read_bytes().count(b'Test Passed.')==14
    plot()
    result['binaries']={name:sha(ROOT/'build-v012/Release'/name) for name in ['VehicleSoundLab.exe','vsl_render.exe']}
    result['files']={str(p.relative_to(OUT)).replace('\\','/'):sha(p) for p in sorted(OUT.rglob('*')) if p.is_file()}
    (OUT/'verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result['device'],indent=2),flush=True)


if __name__=='__main__':main()

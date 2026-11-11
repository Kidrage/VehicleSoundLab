"""Render actual 0.3.0 review files and inspect source-layer behaviour."""
from pathlib import Path
import csv
import hashlib
import json
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/python_deps'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import soundfile as sf

OUT=ROOT/'renders/v0.3.0'
CASES={
    'v10_drive': ['--seconds','30','--width','.8'],
    'v10_lift': ['--seconds','7.5','--scenario','lift','--width','.8'],
    'v10_shifts': ['--seconds','13','--scenario','shifts','--width','.8'],
    'v10_neutral': ['--seconds','8','--scenario','neutral','--width','.8'],
    'v10_5000_light': ['--seconds','6','--rpm','5000','--load','.12','--width','.8'],
    'v10_5000_loaded': ['--seconds','6','--rpm','5000','--load','.85','--width','.8'],
    'v10_5000_overrun': ['--seconds','6','--rpm','5000','--load','-.4','--width','.8'],
    'v10_drive_714': ['--seconds','30','--width','.8','--channels','12'],
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rms_db(x):
    return float(10*np.log10(max(np.mean(x*x),1e-30)))


def trace_plot(name):
    rows=list(csv.DictReader((OUT/f'{name}.csv').open()))
    t=np.array([float(r['seconds']) for r in rows])
    fig,ax=plt.subplots(3,1,figsize=(11,7),sharex=True,constrained_layout=True)
    ax[0].plot(t,[float(r['rpm']) for r in rows],color='#23a18c',label='RPM')
    ax[0].set_ylabel('RPM');ax[0].legend(loc='upper left')
    for key in ['exhaust_gain','body_gain','intake_gain','mechanical_gain','air_gain','high_gain']:
        v=np.array([float(r[key]) for r in rows]);v/=max(v.max(),1e-30)
        ax[1].plot(t,v,label=key.removesuffix('_gain'),linewidth=1.2)
    ax[1].set_ylabel('Each control / own peak')
    ax[1].legend(ncol=3,fontsize=8)
    for key in ['cut_exhaust','cut_body','cut_intake','cut_mechanical','cut_air','cut_high_orders']:
        ax[2].plot(t,[float(r[key]) for r in rows],label=key.removeprefix('cut_'),linewidth=1.2)
    ax[2].set_ylabel('Independent shift gates');ax[2].set_xlabel('Rendered seconds')
    for a in ax:a.grid(alpha=.15)
    fig.suptitle(f'{name} | control traces, not acoustic source-energy measurements')
    fig.savefig(OUT/f'{name}.png',dpi=140);plt.close(fig)
    return rows


def audition_copies():
    report={}
    for label,paths in {
        'drive': [ROOT/'renders/v0.2.0/v10_drive_stereo.wav',OUT/'v10_drive.wav'],
        'loaded': [ROOT/'renders/v0.2.0/v10_5000_loaded.wav',OUT/'v10_5000_loaded.wav'],
        'lift': [OUT/'v10_lift.wav'], 'shifts': [OUT/'v10_shifts.wav'],
        'neutral': [OUT/'v10_neutral.wav'],
    }.items():
        arrays=[sf.read(p,always_2d=True)[0] for p in paths]
        gains=[10**((-23-rms_db(x))/20) for x in arrays]
        common=min(1,.85/max(float(np.abs(x).max())*g for x,g in zip(arrays,gains)))
        for path,x,g in zip(paths,arrays,gains):
            version='v02' if path.parent.name=='v0.2.0' else 'v03'
            target=OUT/f'audition_{label}_{version}.wav'
            sf.write(target,x*g*common,48000,subtype='PCM_24')
            report[target.name]=dict(source=str(path.relative_to(ROOT)),source_sha256=digest(path),
                gain_db=float(20*np.log10(g*common)),rms_dbfs=rms_db(x*g*common),
                method='Non-weighted full-clip RMS alignment, shared peak trim within a pair; not LUFS.')
    return report


def main():
    OUT.mkdir(exist_ok=True);(OUT/'stems').mkdir(exist_ok=True)
    report=dict(version='0.3.0',seed=48271,cases={})
    for name,args in CASES.items():
        command=[str(ROOT/'build/Release/vsl_render.exe'),str(OUT/f'{name}.wav'),*args,
                 '--trace',str(OUT/f'{name}.csv')]
        if name in ['v10_lift','v10_shifts','v10_drive_714']:
            command+=['--stems',str(OUT/f'stems/{name}'),'--scene',str(OUT/f'{name}_scene.json')]
        result=subprocess.run(command,check=True,capture_output=True,text=True)
        assert 'DSP 0.3.0' in result.stdout
        x,sr=sf.read(OUT/f'{name}.wav',always_2d=True)
        assert sr==48000 and np.isfinite(x).all() and np.abs(x).max()<.95
        report['cases'][name]=dict(command=command,sha256=digest(OUT/f'{name}.wav'),
            channels=x.shape[1],frames=len(x),rms_dbfs=rms_db(x),peak_dbfs=float(20*np.log10(np.abs(x).max())))
        rows=trace_plot(name)
        report['cases'][name]['operating']=sorted({r['operating'] for r in rows})
        report['cases'][name]['shifts']=int(rows[-1]['shifts'])
        print(name,report['cases'][name]['operating'])
    # Verify the actual layer files, rather than just their gain controls.
    measurements={}
    for layer in ['exhaust_left','body','intake','mechanical','air_left','events']:
        path=OUT/f'stems/v10_lift_{layer}.wav';x,sr=sf.read(path)
        before=x[int(2.6*sr):int(2.9*sr)];after=x[int(3.12*sr):int(3.22*sr)]
        measurements[layer]=dict(before_rms_dbfs=rms_db(before),after_rms_dbfs=rms_db(after),
            after_minus_before_db=rms_db(after)-rms_db(before) if rms_db(before)>-180 else None,
            comparison_status='level change' if rms_db(before)>-180 else 'no measurable pre-event energy',
            sha256=digest(path))
    assert measurements['body']['after_minus_before_db']>measurements['intake']['after_minus_before_db']+8
    report['lift_stem_measurements']=dict(before_seconds=[2.6,2.9],after_seconds=[3.12,3.22],
        measurements=measurements,limits='Procedural layer response evidence, not fitted physical decay constants.')
    assert report['cases']['v10_shifts']['shifts']>=3
    assert 'FREE REV' in report['cases']['v10_neutral']['operating']
    assert 'OVERRUN' in report['cases']['v10_lift']['operating']
    drive=list(csv.DictReader((OUT/'v10_drive.csv').open()))
    coast=[r for r in drive if 15.1<float(r['seconds'])<17.8]
    assert len({r['gear'] for r in coast})==1 and len({r['shifts'] for r in coast})==1
    braking_downshifts=[]
    for previous,row in zip(drive,drive[1:]):
        if int(row['shifts'])>int(previous['shifts']) and int(row['gear'])<int(previous['gear']):
            assert float(row['wheel_coupled_rpm'])<8500*.90+1
            braking_downshifts.append(row)
    assert braking_downshifts and float(drive[-1]['speed_kph'])<2
    report['sport_auto']=dict(coast_file_seconds=[15.1,17.8],coast_gear=int(coast[0]['gear']),
        extra_coast_shifts=0,safe_downshifts=len(braking_downshifts),braking_downshifts=braking_downshifts,
        final_speed_kph=float(drive[-1]['speed_kph']))
    for scene_path in OUT.glob('*_scene.json'):
        scene=json.loads(scene_path.read_text(encoding='utf-8'))
        for obj in scene['objects']:
            path=Path(obj['file']);obj['sha256']=digest(path)
            obj['file']=str(path.relative_to(OUT)).replace('\\','/')
        scene_path.write_text(json.dumps(scene,indent=2),encoding='utf-8')
    report['audition_copies']=audition_copies()
    report['files']={str(p.relative_to(OUT)).replace('\\','/'):digest(p)
                     for p in sorted(OUT.rglob('*'))
                     if not p.name.startswith('ui_') and (p.suffix in ['.wav','.csv','.png'] or p.name.endswith('_scene.json'))}
    (OUT/'verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report['lift_stem_measurements'],indent=2))


if __name__=='__main__':main()

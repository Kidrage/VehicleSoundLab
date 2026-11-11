"""Focused lifecycle review against frozen V09, retaining shared pair gains."""
import csv
import json
import shutil
import subprocess
from runtime_review import ROOT, render, sha, smoke, scene_paths
from review_pairs import common_pair
import numpy as np
import soundfile as sf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

OUT=ROOT/'renders/v0.10.0'
NEW=ROOT/'build-v010/Release/vsl_render.exe'
OLD=ROOT/'baselines/v0.9.0/bin/vsl_render.exe'
CASES={
    'start':['--throttle','0','--seconds','4'],
    'pure_start':['--throttle','0','--seconds','4','--pure'],
    'neutral':['--scenario','neutral','--seconds','8'],
    'drive':['--scenario','auto','--seconds','30'],
    'shifts':['--scenario','shifts','--seconds','13']
}


def rows(path):
    with path.open(newline='') as file:return list(csv.DictReader(file))


def measurements(report):
    series={tag:rows(OUT/f'start_{tag}.csv') for tag in ['v09','v010']}
    new=series['v010'];catch=[r for r in new if r['lifecycle']=='CATCH']
    entry_index=next(i for i,r in enumerate(new) if r['lifecycle']=='CATCH')
    entry=float(new[entry_index]['rpm']);before=float(new[entry_index-1]['rpm'])
    assert abs(entry-before)<1e-6 and 200<entry<225
    peak=max(float(r['rpm']) for r in catch)
    maxrate=max(abs(float(r['drive_rpm_rate'])) for r in catch)
    assert 1149<peak<1151 and maxrate<8000
    flare=np.array([float(r['lifecycle_flare']) for r in catch])
    assert np.any(np.diff(flare)>0) and np.any(np.diff(flare)<0)
    assert all(float(r['combustion_permission'])==0 for r in new if r['lifecycle']=='CRANK')
    # Fixed-step host scenarios retain actual driving constraints after startup.
    drive=rows(OUT/'drive_v010.csv');shifts=rows(OUT/'shifts_v010.csv')
    lift=[r for r in drive if 14.2<float(r['running_seconds'])<16.8]
    assert lift and len({r['gear'] for r in lift})==1
    assert all(r['shift_stage']=='NONE' for r in lift)
    stop=[r for r in shifts if r['lifecycle'] in ['STOPPING','OFF']]
    assert stop and shifts[-1]['lifecycle']=='OFF'
    assert all(float(r['fuel_command'])==0 and float(r['combustion_permission'])==0 for r in stop)
    fig,axes=plt.subplots(3,1,figsize=(11,9),constrained_layout=True)
    for tag,label in [('v09','V0.9 actual exported trace (coarse)'),('v010','V0.10 actual exported trace')]:
        data=series[tag];t=[float(r['seconds']) for r in data]
        axes[0].plot(t,[float(r['rpm']) for r in data],label=label,lw=1.5)
        for axis,key in zip(axes[1:],['exhaust_gain','mechanical_motion_gain']):
            axis.plot(t,[float(r[key]) for r in data],label=label,lw=1.2)
    for ax,title,ylabel in zip(axes,['Continuous starter / catch / idle','Fired exhaust envelope','Independent rotation-driven mechanical envelope'],['RPM','Linear envelope','Linear envelope']):
        ax.set(title=title,xlim=(0,1.4),xlabel='Rendered seconds',ylabel=ylabel);ax.grid(alpha=.2)
    axes[0].legend();fig.savefig(OUT/'lifecycle_comparison.png',dpi=140);plt.close(fig)
    return dict(catch_entry_rpm=entry,previous_trace_rpm=before,catch_peak_rpm=peak,
        max_observed_control_rate_rpm_s=maxrate,catch_entry_rpm_step=entry-before,
        trace_resolution='New lifecycle: each render chunk, 5.333 ms for fixed scenario; 200 Hz control. Old trace is coarse; no exact old boundary inferred from interpolation.',
        sport_lift_gear=lift[0]['gear'],sport_lift_rows=len(lift),shutdown_gate_rows=len(stop),
        limits='Engineering continuity checks, not vehicle torque identification, timbre acceptance or physical shutdown calibration.')


def main():
    OUT.mkdir(exist_ok=True);(OUT/'stems').mkdir(exist_ok=True)
    report=dict(version='0.10.0',seed=48271,cases={})
    for name,args in CASES.items():
        arrays=[];takes={}
        for tag,exe,ver in [('v09',OLD,'0.9.0'),('v010',NEW,'0.10.0')]:
            x,info=render(exe,OUT/f'{name}_{tag}.wav',args,ver,
                ['--trace',str(OUT/f'{name}_{tag}.csv'),'--stems',str(OUT/f'stems/{name}_{tag}')])
            arrays.append(x);takes[tag]=info
        copies=common_pair(OUT,arrays,['v09','v010'],name)
        for tag in takes:takes[tag]['audition']=copies[tag]
        report['cases'][name]=takes
        print(name,'shared-gain pair rendered',flush=True)
    _,report['bed714']=render(NEW,OUT/'drive_714.wav',CASES['drive']+['--channels','12'],'0.10.0',
        ['--stems',str(OUT/'stems/drive_714'),'--scene',str(OUT/'drive_714_scene.json')])
    scene_paths(OUT/'drive_714_scene.json',OUT)
    for obj in json.loads((OUT/'drive_714_scene.json').read_text())['objects']:
        assert (OUT/obj['file']).read_bytes()==(OUT/f'stems/drive_v010_{obj["name"]}.wav').read_bytes()
    report['stereo_714_source_equality']=10
    report['measurements']=measurements(report)
    report['device']=smoke(ROOT/'build-v010',OUT,'0.10.0')
    for name in ['ui_control_roundtrip.ini','ui_legacy_preset.ini','ui_v08_preset.ini']:
        shutil.copy2(ROOT/'renders'/name,OUT/name)
    for key in ['fuel_controls','fuel_preset_roundtrip','control_isolation','mechanical_control','mechanical_preset_roundtrip',
        'legacy_preset_retains_mechanical_voice','combustion_control','combustion_preset_roundtrip','legacy_preset_retains_pressure_voice']:
        assert report['device'][key],key
    report['binaries']={name:sha(ROOT/'build-v010/Release'/name) for name in ['VehicleSoundLab.exe','vsl_render.exe']}
    report['files']={str(p.relative_to(OUT)).replace('\\','/'):sha(p) for p in sorted(OUT.rglob('*')) if p.is_file() and p.name!='verification.json'}
    (OUT/'verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(dict(measurements=report['measurements'],device=report['device']),indent=2))


if __name__=='__main__':main()

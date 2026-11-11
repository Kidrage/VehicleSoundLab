"""Review physical clutch/engine integration against frozen V012."""
import json
import shutil
from runtime_review import ROOT,render,sha,smoke,scene_paths
from review_pairs import common_pair
from drivetrain_audit import read_trace,metrics,energy_audit
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

OUT=ROOT/'renders/v0.13.0'
OLD=ROOT/'baselines/v0.12.0/bin/vsl_render.exe'
NEW=ROOT/'build-v013/Release/vsl_render.exe'
CASES={
    'drive':['--scenario','auto','--seconds','30','--width','.8'],
    'downshift':['--scenario','downshift','--seconds','18','--width','.8'],
    'shifts':['--scenario','shifts','--seconds','13','--width','.8'],
    'neutral':['--scenario','neutral','--seconds','8','--width','.8']}


def plot():
    old=read_trace(OUT/'drive_v012.csv');new=read_trace(OUT/'drive_v013.csv')
    fig,axes=plt.subplots(5,1,figsize=(11,11),sharex=True)
    for tag,rows,style in [('V012',old,'--'),('V013',new,'-')]:
        t=[float(r['seconds']) for r in rows]
        axes[0].plot(t,[float(r['rpm']) for r in rows],style,label=tag,lw=1.3)
        axes[1].plot(t,[float(r['speed_kph']) for r in rows],style,label=tag,lw=1.3)
        axes[2].plot(t,[int(r['gear']) for r in rows],style,label=tag,lw=1.3)
    for axis,label in zip(axes[:3],['RPM','Speed (km/h)','Gear']):axis.set_ylabel(label)
    t=[float(r['seconds']) for r in new]
    for key,label in [('clutch_torque_nm','Clutch torque'),('shaft_torque_nm','Net engine torque'),('governor_reduction_nm','Explicit torque reduction')]:
        axes[3].plot(t,[float(r[key]) for r in new],label=label,lw=1)
    axes[3].set_ylabel('Torque (Nm)')
    for key,label in [('total_clutch_heat_j','Clutch friction'),('total_transmission_loss_j','Transmission'),('total_numerical_loss_j','Numerical damping')]:
        axes[4].plot(t,[float(r[key])/1000 for r in new],label=label,lw=1.3)
    axes[4].set_ylabel('Accumulated loss (kJ)');axes[4].set_xlabel('Export time (s)')
    for axis in axes:axis.grid(alpha=.2);axis.legend(loc='upper left',ncol=3,fontsize=8)
    fig.suptitle('Same pedal scenario; coupled physical inertias. Engineering vehicle proxy, not car telemetry.')
    fig.tight_layout();fig.savefig(OUT/'coupled_driving.png',dpi=140);plt.close(fig)


def main():
    if (OUT/'verification.json').exists():raise SystemExit('Final V013 review already exists; preserve it.')
    OUT.mkdir(parents=True,exist_ok=True);(OUT/'stems').mkdir(exist_ok=True)
    result=dict(version='0.13.0',seed=48271,cases={},bench_unchanged={})
    for name,args in CASES.items():
        arrays=[];takes={}
        for tag,exe,ver in [('v012',OLD,'0.12.0'),('v013',NEW,'0.13.0')]:
            extra=['--trace',str(OUT/f'{name}_{tag}.csv')]
            if name=='drive':extra+=['--stems',str(OUT/f'stems/drive_{tag}')]
            x,info=render(exe,OUT/f'{name}_{tag}.wav',args,ver,extra)
            rows=read_trace(OUT/f'{name}_{tag}.csv');info['driving']=metrics(rows)
            if tag=='v013':info['energy']=energy_audit(rows)
            arrays.append(x);takes[tag]=info
        auditions=common_pair(OUT,arrays,['v012','v013'],name)
        for tag in takes:takes[tag]['audition']=auditions[tag]
        result['cases'][name]=takes
        print(name,json.dumps(dict(driving=takes['v013']['driving'],energy=takes['v013']['energy'])),flush=True)
    for name,args in {
        'low':['--rpm','1200','--load','.18','--seconds','4.2'],
        'high':['--rpm','8000','--load','.85','--seconds','4.2'],
        'lift':['--scenario','lift','--seconds','7.5'],
        'imported':['--rpm','4000','--load','.65','--seconds','4.2','--dna',str(ROOT/'renders/v0.9.0/dna_check/known_steady_harmonics.dna')]}.items():
        files=[]
        for tag,exe,ver in [('v012',OLD,'0.12.0'),('v013',NEW,'0.13.0')]:
            path=OUT/f'bench_{name}_{tag}.wav';render(exe,path,args,ver);files.append(path)
        assert files[0].read_bytes()==files[1].read_bytes(),name
        result['bench_unchanged'][name]=sha(files[1]);print('unchanged bench',name,flush=True)
    _,result['bed714']=render(NEW,OUT/'drive_714.wav',CASES['drive']+['--channels','12'],'0.13.0',
        ['--stems',str(OUT/'stems/drive_714'),'--scene',str(OUT/'drive_714_scene.json')])
    scene_paths(OUT/'drive_714_scene.json',OUT)
    for obj in json.loads((OUT/'drive_714_scene.json').read_text())['objects']:
        assert (OUT/obj['file']).read_bytes()==(OUT/f'stems/drive_v013_{obj["name"]}.wav').read_bytes()
    result['stereo_714_identical_sources']=10
    result['device']=smoke(ROOT/'build-v013',OUT,'0.13.0');assert result['device']['two_inertia_coupling_active']
    for name in ['ui_control_roundtrip.ini','ui_legacy_preset.ini','ui_v08_preset.ini']:
        shutil.copy2(ROOT/'renders'/name,OUT/name)
    shutil.copy2(ROOT/'build-v013/Testing/Temporary/LastTest.log',OUT/'ctest.log')
    assert (OUT/'ctest.log').read_bytes().count(b'Test Passed.')==15
    plot()
    result['binaries']={name:sha(ROOT/'build-v013/Release'/name) for name in ['VehicleSoundLab.exe','vsl_render.exe']}
    result['files']={str(p.relative_to(OUT)).replace('\\','/'):sha(p) for p in sorted(OUT.rglob('*')) if p.is_file()}
    (OUT/'verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result['device'],indent=2),flush=True)


if __name__=='__main__':main()

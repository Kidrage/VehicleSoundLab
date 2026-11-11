"""Continuous main-bank spectrum against frozen V010; shared gains and objects."""
import csv
import json
import shutil
import sys
from runtime_review import ROOT,render as render_new,sha,smoke,scene_paths,rms
from review_pairs import common_pair
from inspect_spectral_handoff import amplitudes,RPMS
import numpy as np
import soundfile as sf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

OUT=ROOT/'renders/v0.11.0'
NEW=ROOT/'build-v011/Release/vsl_render.exe'
OLD=ROOT/'baselines/v0.10.0/bin/vsl_render.exe'
REUSE='--reuse-rendered' in sys.argv
CASES={
 'low':['--rpm','1200','--load','.18','--seconds','4.2','--width','.8'],
 'idle':['--rpm','850','--load','.12','--seconds','4.2','--width','.8'],
 'mid':['--rpm','4000','--load','.65','--seconds','4.2','--width','.8'],
 'high':['--rpm','8000','--load','.85','--seconds','4.2','--width','.8'],
 'pure_low':['--rpm','1200','--load','.18','--seconds','4.2','--width','.8','--pure','--irregularity','0'],
 'lift':['--scenario','lift','--seconds','7.5','--width','.8'],
 'neutral':['--scenario','neutral','--seconds','8','--width','.8'],
 'downshift':['--scenario','downshift','--seconds','18','--width','.8'],
 'drive':['--scenario','auto','--seconds','30','--width','.8']}


def render(exe,path,args,version,extra=()):
    if not REUSE:return render_new(exe,path,args,version,extra)
    # Recover completed exports after an audit-only failure without rerunning
    # renders/device tests. The command, current binaries and raw files remain
    # explicit; a later rebuilt binary invalidates this recovery path.
    assert path.stat().st_mtime_ns>exe.stat().st_mtime_ns
    x,sr=sf.read(path,always_2d=True)
    assert sr==48000 and np.isfinite(x).all() and abs(x).max()<.95
    return x,dict(command=[str(exe),str(path),*args,*extra],sha256=sha(path),
        frames=len(x),channels=x.shape[1],rms_dbfs=rms(x),peak=float(abs(x).max()),
        recovery='Revalidated completed export after UTF-8 decoding failure in CTest log audit; no renderer/device restart.')


def handoff():
    folder=OUT/'handoff';folder.mkdir(exist_ok=True)
    old_root=ROOT/'references/analysis/spectral_handoff_v1'
    previous=json.loads((old_root/'results.json').read_text())
    result={};fig,axes=plt.subplots(2,1,figsize=(12,9),constrained_layout=True)
    for load,ax in zip([.18,.85],axes):
        takes={}
        for rpm in RPMS:
            name=f'rpm{rpm}_load{int(load*100)}'
            _,info=render(NEW,folder/f'{name}.wav',['--rpm',str(rpm),'--load',str(load),'--pure',
                '--irregularity','0','--seconds','4.2'],'0.11.0',['--stems',str(folder/name)])
            amplitude=amplitudes(folder/f'{name}_exhaust_left.wav',rpm)
            old_amplitude=previous['cases'][str(load)][str(rpm)]['bank_order_amplitudes']
            a,b=[20*np.log10(np.maximum(x,1e-20)) for x in [old_amplitude,amplitude]]
            assert max(abs(np.diff(b[24:29])))<6
            assert max(abs((b-a)[14:25]))<.002
            color=f'C{RPMS.index(rpm)}'
            ax.plot(np.arange(1,61),a,lw=.7,ls='--',alpha=.55,color=color)
            ax.plot(np.arange(1,61),b,lw=.9,label=f'{rpm} RPM',color=color)
            takes[str(rpm)]=dict(render=info,amplitudes=amplitude,
                old_order26_to25_db=float(a[25]-a[24]),new_order26_to25_db=float(b[25]-b[24]),
                maximum_adjacent_step_orders25_29_db=float(max(abs(np.diff(b[24:29])))),
                max_orders15_25_change_db=float(max(abs((b-a)[14:25]))),
                old_source=str((old_root/f'{name}_exhaust_left.wav').relative_to(ROOT)).replace('\\','/'),
                old_source_sha256=sha(old_root/f'{name}_exhaust_left.wav'))
        ax.axvline(25.6,color='black',ls=':',alpha=.5)
        ax.set(title=f'Actual source amplitudes, load {load}: V010 dashed / V011 solid',
            xlabel='Bank harmonic order',ylabel='dBFS amplitude',xlim=(15,55),ylim=(-115,-30));ax.grid(alpha=.2);ax.legend(ncol=3)
        result[str(load)]=takes
    fig.savefig(OUT/'spectral_handoff.png',dpi=140);plt.close(fig)
    return dict(cases=result,analysis='Hann projection 2-4 s, actual float source; default detail .55, zero irregularity, Pure OSC. Orders 15-25 unchanged; principal bank orders only.',
        original_analysis_sha256=sha(old_root/'results.json'),limits='Continuity/phase checks do not establish measured car spectrum, perceived naturalness or separated acoustic transfer.')


def main():
    OUT.mkdir(exist_ok=True);(OUT/'stems').mkdir(exist_ok=True)
    report=dict(version='0.11.0',seed=48271,cases={})
    for name,args in CASES.items():
        arrays=[];takes={}
        for tag,exe,version in [('v010',OLD,'0.10.0'),('v011',NEW,'0.11.0')]:
            x,info=render(exe,OUT/f'{name}_{tag}.wav',args,version,
                ['--stems',str(OUT/f'stems/{name}_{tag}'),'--trace',str(OUT/f'{name}_{tag}.csv')])
            arrays.append(x);takes[tag]=info
        copies=common_pair(OUT,arrays,['v010','v011'],name)
        for tag in takes:takes[tag]['audition']=copies[tag]
        assert (OUT/f'{name}_v010.csv').read_bytes()==(OUT/f'{name}_v011.csv').read_bytes()
        unchanged=[]
        for file in sorted((OUT/'stems').glob(f'{name}_v010_*.wav')):
            if any(file.stem.endswith('_'+s) for s in ['exhaust_left','exhaust_right','body']):continue
            assert file.read_bytes()==file.with_name(file.name.replace('_v010_','_v011_')).read_bytes(),file.name
            unchanged.append(file.name)
        assert len(unchanged)==7;takes['unchanged_objects']=unchanged
        report['cases'][name]=takes;print(name,'pair revalidated' if REUSE else 'pair rendered','; driving and seven other objects identical',flush=True)
    report['handoff']=handoff()
    report['other_templates_bit_identical']={}
    for profile in range(1,5):
        files=[]
        for tag,exe,ver in [('v010',OLD,'0.10.0'),('v011',NEW,'0.11.0')]:
            file=OUT/f'compat_profile{profile}_{tag}.wav';render(exe,file,['--profile',str(profile),'--rpm','4000','--load','.65','--seconds','3'],ver);files.append(file)
        assert files[0].read_bytes()==files[1].read_bytes();report['other_templates_bit_identical'][str(profile)]=sha(files[0])
    for label,args in [('detail_zero',CASES['pure_low']+['--detail','0']),
            ('imported',CASES['lift']+['--dna',str(ROOT/'renders/v0.9.0/dna_check/known_steady_harmonics.dna')])]:
        files=[]
        for tag,exe,ver in [('v010',OLD,'0.10.0'),('v011',NEW,'0.11.0')]:
            file=OUT/f'compat_{label}_{tag}.wav';render(exe,file,args,ver);files.append(file)
        assert files[0].read_bytes()==files[1].read_bytes();report[label+'_bit_identical']=True
    _,report['bed714']=render(NEW,OUT/'drive_714.wav',CASES['drive']+['--channels','12'],'0.11.0',
        ['--stems',str(OUT/'stems/drive_714'),'--scene',str(OUT/'drive_714_scene.json')])
    if not REUSE:scene_paths(OUT/'drive_714_scene.json',OUT)
    for obj in json.loads((OUT/'drive_714_scene.json').read_text())['objects']:
        assert (OUT/obj['file']).read_bytes()==(OUT/f'stems/drive_v011_{obj["name"]}.wav').read_bytes()
    report['stereo_714_identical_sources']=10
    report['device']=json.loads((OUT/'ui_smoke.json').read_text()) if REUSE else smoke(ROOT/'build-v011',OUT,'0.11.0')
    for name in ['ui_control_roundtrip.ini','ui_legacy_preset.ini','ui_v08_preset.ini']:shutil.copy2(ROOT/'renders'/name,OUT/name)
    shutil.copy2(ROOT/'build-v011/Testing/Temporary/LastTest.log',OUT/'ctest.log')
    assert (OUT/'ctest.log').read_bytes().count(b'Test Passed.')==13
    report['binaries']={name:sha(ROOT/'build-v011/Release'/name) for name in ['VehicleSoundLab.exe','vsl_render.exe']}
    report['files']={str(p.relative_to(OUT)).replace('\\','/'):sha(p) for p in sorted(OUT.rglob('*')) if p.is_file() and p.name!='verification.json'}
    (OUT/'verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(dict(device=report['device'],handoff={load:{rpm:round(item['new_order26_to25_db'],3) for rpm,item in takes.items()} for load,takes in report['handoff']['cases'].items()}),indent=2))


if __name__=='__main__':main()

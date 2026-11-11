"""Preserved legacy vs driven mechanics, common gain, independent source export."""
from pathlib import Path
import csv
import json
import shutil
import subprocess
import sys
from runtime_review import ROOT,render,sha,smoke,scene_paths,rms
from render_v07_review import traces
import numpy as np
import soundfile as sf

OUT=ROOT/'renders/v0.8.0'
NEW=ROOT/'build-v08/Release/vsl_render.exe'
OLD=ROOT/'baselines/v0.7.0/bin/vsl_render.exe'
CASES={
    'idle':['--rpm','850','--load','.12','--seconds','4','--width','.8'],
    'mid':['--rpm','4000','--load','.65','--seconds','4','--width','.8'],
    'high':['--rpm','8000','--load','.85','--seconds','4','--width','.8'],
    'lift':['--scenario','lift','--seconds','7.5','--width','.8'],
    'neutral':['--scenario','neutral','--seconds','8','--width','.8'],
    'shifts':['--scenario','shifts','--seconds','13.5','--width','.8'],
    'downshift':['--scenario','downshift','--seconds','18','--width','.8'],
    'drive':['--seconds','30','--width','.8']}
TAGS=['legacy','driven']


def common_pair(arrays,name):
    gain=min(10**((-23-max(map(rms,arrays)))/20),.85/max(float(abs(x).max()) for x in arrays))
    result={}
    for tag,x in zip(TAGS,arrays):
        path=OUT/f'audition_{name}_{tag}.wav';sf.write(path,x*gain,48000,subtype='PCM_24')
        result[tag]=dict(file=path.name,sha256=sha(path),channels=sf.info(path).channels,
            gain_db=float(20*np.log10(gain)),raw_rms_dbfs=rms(x),
            processing='One shared constant gain per pair; louder full clip at -23 dBFS RMS, pair peak <=0.85. No individual normalization, compression or denoising.')
    return result


def update_files(report):
    excluded={'verification.json','workspace_audit.json','mechanical_measurements.json','browser_qa.json',
        'listening_desktop.png','listening_mobile.png','mechanical_spectra.png','mechanical_states.png','ui_native_preview.png'}
    report['files']={str(p.relative_to(OUT)).replace('\\','/'):sha(p) for p in sorted(OUT.rglob('*'))
        if p.is_file() and p.name not in excluded}
    report['binaries']={name:sha(ROOT/'build-v08/Release'/name) for name in ['VehicleSoundLab.exe','vsl_render.exe']}
    (OUT/'verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')


def main():
    OUT.mkdir(exist_ok=True);(OUT/'stems').mkdir(exist_ok=True)
    report=dict(version='0.8.0',seed=48271,cases={},legacy_compatibility={},isolated={})
    for name,args in CASES.items():
        arrays=[];takes={}
        for tag,model in zip(TAGS,[0,1]):
            extra=['--mechanical-model',str(model),'--trace',str(OUT/f'{name}_{tag}.csv')]
            if name in ['idle','mid','high','lift','shifts','downshift','drive']:
                extra+=['--stems',str(OUT/f'stems/{name}_{tag}')]
            x,info=render(NEW,OUT/f'{name}_{tag}.wav',args,'0.8.0',extra)
            arrays.append(x);takes[tag]=info
        copies=common_pair(arrays,name)
        for tag in TAGS:takes[tag]['audition']=copies[tag]
        previous=OUT/f'{name}_v07.wav'
        render(OLD,previous,args,'0.7.0',['--trace',str(OUT/f'{name}_v07.csv')])
        assert previous.read_bytes()==(OUT/f'{name}_legacy.wav').read_bytes(),name
        rows=traces(OUT/f'{name}_v07.csv',OUT/f'{name}_driven.csv')
        report['legacy_compatibility'][name]=dict(bypass_bit_identical=True,old_trace_rows_verified=rows)
        if name in ['idle','mid','high','lift','shifts','downshift','drive']:
            stem_files=sorted((OUT/'stems').glob(f'{name}_legacy_*.wav'))
            unaffected=[]
            for path in stem_files:
                other=path.with_name(path.name.replace('_legacy_','_driven_'))
                if path.stem.endswith('_mechanical'):continue
                assert path.read_bytes()==other.read_bytes(),path.name
                unaffected.append(path.name)
            assert len(unaffected)==9
            report['legacy_compatibility'][name]['unchanged_source_stems']=unaffected
        report['cases'][name]=takes
        print(name,'legacy audio reproducible; old driving trace preserved',flush=True)
    for name in ['idle','mid','high','lift','shifts']:
        arrays=[sf.read(OUT/f'stems/{name}_{tag}_mechanical.wav')[0] for tag in TAGS]
        report['isolated'][name]=common_pair(arrays,'mechanical_'+name)
    report['template_bypass']={}
    for profile in range(5):
        paths=[]
        for tag,exe,ver,extra in [('v07',OLD,'0.7.0',[]),('v08',NEW,'0.8.0',['--mechanical-model','0'])]:
            path=OUT/f'compat_profile{profile}_{tag}.wav'
            render(exe,path,['--profile',str(profile),'--rpm','4000','--load','.65','--seconds','3'],ver,extra);paths.append(path)
        assert paths[0].read_bytes()==paths[1].read_bytes(),profile
        report['template_bypass'][str(profile)]=sha(paths[0])
    # The modal source keeps running internally but the Pure OSC path stays unchanged.
    paths=[]
    for tag,exe,ver in [('v07',OLD,'0.7.0'),('v08',NEW,'0.8.0')]:
        path=OUT/f'lift_pure_{tag}.wav';render(exe,path,CASES['lift']+['--pure'],ver);paths.append(path)
    assert paths[0].read_bytes()==paths[1].read_bytes();report['pure_osc_bit_identical']=True
    _,report['bed714']=render(NEW,OUT/'drive_714_v08.wav',CASES['drive']+['--channels','12'],'0.8.0',
        ['--stems',str(OUT/'stems/drive_714'),'--scene',str(OUT/'drive_714_scene.json')])
    scene_paths(OUT/'drive_714_scene.json',OUT)
    for obj in json.loads((OUT/'drive_714_scene.json').read_text())['objects']:
        path=OUT/obj['file'];assert path.read_bytes()==(OUT/f'stems/drive_driven_{obj["name"]}.wav').read_bytes(),obj['name']
    report['stereo_714_stems_bit_identical']=10
    subprocess.run([sys.executable,str(ROOT/'tools/check_dna_pipeline.py'),'--renderer',str(NEW),'--out',str(OUT/'dna_check')],check=True)
    report['device']=smoke(ROOT/'build-v08',OUT,'0.8.0')
    assert all(report['device'][key] for key in ['fuel_controls','fuel_preset_roundtrip','control_isolation','mechanical_control','mechanical_preset_roundtrip','legacy_preset_retains_mechanical_voice'])
    shutil.copy2(ROOT/'renders/ui_control_roundtrip.ini',OUT/'ui_control_roundtrip.ini')
    shutil.copy2(ROOT/'renders/ui_legacy_preset.ini',OUT/'ui_legacy_preset.ini')
    report['limits']=[
        'Mode frequencies, damping, strike weights and ideal 360/540 degree timing are engineering settings, not identified Lamborghini block/cam data.',
        'Mixed exterior/cabin recordings cannot uniquely separate mechanical modes from exhaust orders, intake, reflections or recording processing.',
        'New mechanics is one pre-spatial source, with separate rotational/fired RNG; no duplicated engine or arbitrary height widening.',
        'Numerical timing/decay, preserved vehicle state and muted device checks do not prove subjective realism or physical 7.1.4 playback.',
        'RPM/load spectra, intake/exhaust transfer, physical torque/inertia, cycle realism and synchronized video telemetry remain incomplete.']
    update_files(report)
    print(json.dumps(dict(device=report['device'],cases=len(report['cases']),isolated=len(report['isolated'])),indent=2))


if __name__=='__main__':
    if '--device-only' in sys.argv:
        report=json.loads((OUT/'verification.json').read_text())
        report['device']=smoke(ROOT/'build-v08',OUT,'0.8.0')
        assert all(report['device'][key] for key in ['fuel_controls','fuel_preset_roundtrip','control_isolation','mechanical_control','mechanical_preset_roundtrip','legacy_preset_retains_mechanical_voice'])
        for name in ['ui_control_roundtrip.ini','ui_legacy_preset.ini']:shutil.copy2(ROOT/'renders'/name,OUT/name)
        update_files(report);print(json.dumps(report['device'],indent=2))
    else:main()

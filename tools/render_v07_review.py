"""Compare fuel-aware excitation against its bypass, with shared audition gain."""
from pathlib import Path
import csv
import json
import subprocess
import sys
from runtime_review import ROOT,render,sha,smoke,scene_paths,rms
import numpy as np
import soundfile as sf

OUT=ROOT/'renders/v0.7.0'
NEW=ROOT/'build-v07/Release/vsl_render.exe'
OLD=ROOT/'baselines/v0.6.0/bin/vsl_render.exe'
CASES={
    'lift':['--scenario','lift','--seconds','7.5','--width','.8'],
    'lift_pure':['--scenario','lift','--seconds','7.5','--width','.8','--pure'],
    'downshift':['--scenario','downshift','--seconds','18','--width','.8'],
    'neutral':['--scenario','neutral','--seconds','8','--width','.8'],
    'drive':['--seconds','30','--width','.8']}


def file_manifest():
    derived={'verification.json','workspace_audit.json','browser_qa.json','excitation_measurements.json',
        'dry_lift_sources.png','downshift_fueling.png','listening_desktop.png','listening_mobile.png','ui_native_preview.png'}
    return {str(p.relative_to(OUT)).replace('\\','/'):sha(p) for p in sorted(OUT.rglob('*'))
            if p.is_file() and p.name not in derived}


def binary_manifest():
    return {name:sha(ROOT/'build-v07/Release'/name) for name in ['VehicleSoundLab.exe','vsl_render.exe']}


def common_gain(arrays,name):
    # One scalar for both takes preserves the cut-induced relative level.
    gain=min(10**((-23-max(map(rms,arrays)))/20),.85/max(float(abs(x).max()) for x in arrays))
    result={}
    for tag,x in zip(['bypass','enabled'],arrays):
        file=OUT/f'audition_{name}_{tag}.wav'
        sf.write(file,x*gain,48000,subtype='PCM_24')
        result[tag]=dict(file=file.name,sha256=sha(file),gain_db=float(20*np.log10(gain)),
            processing='Single shared constant gain per pair; louder take limited to -23 dBFS full-clip RMS, pair peak <=0.85. No independent RMS or LUFS matching.')
    return result


def traces(old,new):
    with old.open() as file:before=list(csv.DictReader(file))
    with new.open() as file:after=list(csv.DictReader(file))
    by_time={x['seconds']:x for x in after}
    for row in before:
        assert row['seconds'] in by_time,row['seconds']
        assert all(value==by_time[row['seconds']][key] for key,value in row.items()),row['seconds']
    return len(before)


def main():
    OUT.mkdir(exist_ok=True);(OUT/'stems').mkdir(exist_ok=True)
    report=dict(version='0.7.0',seed=48271,cases={},legacy_compatibility={})
    for name,args in CASES.items():
        arrays=[];takes={}
        for tag,enabled in [('bypass',0),('enabled',1)]:
            extra=['--fuel-cut',str(enabled),'--trace',str(OUT/f'{name}_{tag}.csv')]
            if name=='downshift' and enabled:extra+=['--stems',str(OUT/'stems/downshift')]
            x,info=render(NEW,OUT/f'{name}_{tag}.wav',args,'0.7.0',extra)
            arrays.append(x);takes[tag]=info
        copies=common_gain(arrays,name)
        for tag,item in copies.items():takes[tag]['audition']=item
        old_path=OUT/f'{name}_v06.wav'
        render(OLD,old_path,args,'0.6.0',['--trace',str(OUT/f'{name}_v06.csv')])
        assert old_path.read_bytes()==(OUT/f'{name}_bypass.wav').read_bytes(),name
        count=traces(OUT/f'{name}_v06.csv',OUT/f'{name}_enabled.csv')
        report['legacy_compatibility'][name]=dict(bypass_wav_bit_identical=True,old_trace_rows_verified=count)
        report['cases'][name]=takes
        print(name,'old sound reproducible with bypass; vehicle history unchanged',flush=True)
    # Dry diagnostic isolates body/mechanics from the intentional DNA->IR return.
    report['dry_lift']={}
    for tag,enabled in [('bypass',0),('enabled',1),('no_pump',1)]:
        extra=['--fuel-cut',str(enabled),'--space','0','--trace',str(OUT/f'dry_lift_{tag}.csv'),
            '--stems',str(OUT/f'stems/dry_lift_{tag}')]
        if tag=='no_pump':extra+=['--pumping','0']
        _,info=render(NEW,OUT/f'dry_lift_{tag}.wav',CASES['lift'],'0.7.0',extra)
        report['dry_lift'][tag]=info
    report['steady_compatibility']={}
    for profile in range(5):
        paths=[]
        for tag,exe,version in [('v06',OLD,'0.6.0'),('v07',NEW,'0.7.0')]:
            path=OUT/f'compat_profile{profile}_{tag}.wav'
            render(exe,path,['--profile',str(profile),'--rpm','4000','--load','.65','--seconds','3'],version);paths.append(path)
        assert paths[0].read_bytes()==paths[1].read_bytes(),profile
        report['steady_compatibility'][str(profile)]=sha(paths[0])
    _,report['bed714']=render(NEW,OUT/'drive_714_v07.wav',['--seconds','30','--width','.8','--channels','12'],'0.7.0',
        ['--stems',str(OUT/'stems/drive_714'),'--scene',str(OUT/'drive_714_scene.json')])
    scene_paths(OUT/'drive_714_scene.json',OUT)
    subprocess.run([sys.executable,str(ROOT/'tools/check_dna_pipeline.py'),'--renderer',str(NEW),'--out',str(OUT/'dna_check')],check=True)
    report['device']=smoke(ROOT/'build-v07',OUT,'0.7.0')
    assert report['device']['fuel_controls'] and report['device']['fuel_preset_roundtrip'] and report['device']['control_isolation']
    from shutil import copy2
    copy2(ROOT/'renders/ui_control_roundtrip.ini',OUT/'ui_control_roundtrip.ini')
    report['limits']=[
        'Fuel-cut eligibility/dwell/hysteresis and cavity are engineering settings, not measured Performante ECU or manifold data.',
        'Recorded energy drops do not prove fuel cut; current sources lack synchronized pedal/injector/RPM telemetry.',
        'Firing gate changes pressure excitation while the existing lifecycle/shift envelopes, rotational sound and independent clocks remain active.',
        'Sustained mechanical tones, cycle variation and physical torque/pipe/room calibration remain incomplete.',
        'Muted device tests and a 7.1.4 speaker bed do not establish subjective realism or array playback.']
    report['files']=file_manifest();report['binaries']=binary_manifest()
    (OUT/'verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report['device'],indent=2),flush=True)


if __name__=='__main__':
    if '--device-only' in sys.argv:
        report=json.loads((OUT/'verification.json').read_text())
        report['device']=smoke(ROOT/'build-v07',OUT,'0.7.0')
        assert all(report['device'][key] for key in ['fuel_controls','fuel_preset_roundtrip','control_isolation'])
        from shutil import copy2
        copy2(ROOT/'renders/ui_control_roundtrip.ini',OUT/'ui_control_roundtrip.ini')
        report['files']=file_manifest();report['binaries']=binary_manifest()
        (OUT/'verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps(report['device'],indent=2))
    else:main()

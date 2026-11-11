"""Pressure-event variation against exact V08 bypass and source routing."""
import json
import shutil
import subprocess
import sys
from runtime_review import ROOT,render,sha,smoke,scene_paths
from render_v07_review import traces
from render_v08_review import CASES as PREVIOUS_CASES
from review_pairs import common_pair
import numpy as np
import soundfile as sf
OUT=ROOT/'renders/v0.9.0'
NEW=ROOT/'build-v09/Release/vsl_render.exe'
OLD=ROOT/'baselines/v0.8.0/bin/vsl_render.exe'
CASES=dict(PREVIOUS_CASES)
CASES['stress']=['--rpm','4000','--load','.65','--seconds','6','--width','.8','--irregularity','1']
TAGS=['bypass','varied']
DEVICE_KEYS=['fuel_controls','fuel_preset_roundtrip','control_isolation','mechanical_control','mechanical_preset_roundtrip',
    'legacy_preset_retains_mechanical_voice','combustion_control','combustion_preset_roundtrip','legacy_preset_retains_pressure_voice']


def update_files(report):
    excluded={'verification.json','workspace_audit.json','pressure_measurements.json','browser_qa.json',
        'listening_desktop.png','listening_mobile.png','pressure_spectra.png','pressure_states.png','ui_native_preview.png'}
    report['files']={str(p.relative_to(OUT)).replace('\\','/'):sha(p) for p in sorted(OUT.rglob('*'))
        if p.is_file() and p.name not in excluded}
    report['binaries']={name:sha(ROOT/'build-v09/Release'/name) for name in ['VehicleSoundLab.exe','vsl_render.exe']}
    (OUT/'verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')


def device(report):
    report['device']=smoke(ROOT/'build-v09',OUT,'0.9.0');assert all(report['device'][key] for key in DEVICE_KEYS)
    for name in ['ui_control_roundtrip.ini','ui_legacy_preset.ini','ui_v08_preset.ini']:shutil.copy2(ROOT/'renders'/name,OUT/name)


def main():
    OUT.mkdir(exist_ok=True);(OUT/'stems').mkdir(exist_ok=True)
    report=dict(version='0.9.0',seed=48271,cases={},legacy_compatibility={},isolated={})
    for name,args in CASES.items():
        arrays=[];takes={}
        for tag,enabled in zip(TAGS,[0,1]):
            extra=['--combustion-variation',str(enabled),'--trace',str(OUT/f'{name}_{tag}.csv'),
                '--stems',str(OUT/f'stems/{name}_{tag}')]
            x,info=render(NEW,OUT/f'{name}_{tag}.wav',args,'0.9.0',extra);arrays.append(x);takes[tag]=info
        copies=common_pair(OUT,arrays,TAGS,name)
        for tag in TAGS:takes[tag]['audition']=copies[tag]
        report['cases'][name]=takes
        compat={}
        if name!='stress':
            previous=OUT/f'{name}_v08.wav';render(OLD,previous,args,'0.8.0',['--trace',str(OUT/f'{name}_v08.csv')])
            assert previous.read_bytes()==(OUT/f'{name}_bypass.wav').read_bytes(),name
            compat.update(bypass_bit_identical=True,old_trace_rows_verified=traces(OUT/f'{name}_v08.csv',OUT/f'{name}_varied.csv'))
        unaffected=[]
        for file in sorted((OUT/'stems').glob(f'{name}_bypass_*.wav')):
            if any(file.stem.endswith('_'+s) for s in ['exhaust_left','exhaust_right','body']):continue
            assert file.read_bytes()==file.with_name(file.name.replace('_bypass_','_varied_')).read_bytes(),file.name
            unaffected.append(file.name)
        assert len(unaffected)==7;compat['unchanged_source_stems']=unaffected
        report['legacy_compatibility'][name]=compat
        print(name,'pressure pair rendered; independent driving and seven other objects unchanged',flush=True)
    for name in ['idle','mid','high']:
        arrays=[np.column_stack([sf.read(OUT/f'stems/{name}_{tag}_exhaust_{side}.wav')[0] for side in ['left','right']]) for tag in TAGS]
        report['isolated'][name]=common_pair(OUT,arrays,TAGS,'banks_'+name)
    report['template_bypass']={};report['other_templates_bit_identical']={}
    for profile in range(5):
        paths=[]
        for tag,exe,version,extra in [('v08',OLD,'0.8.0',[]),('bypass',NEW,'0.9.0',['--combustion-variation','0'])]:
            file=OUT/f'compat_profile{profile}_{tag}.wav';render(exe,file,['--profile',str(profile),'--rpm','4000','--load','.65','--seconds','3'],version,extra);paths.append(file)
        assert paths[0].read_bytes()==paths[1].read_bytes();report['template_bypass'][str(profile)]=sha(paths[0])
        if profile:
            file=OUT/f'compat_profile{profile}_enabled.wav';render(NEW,file,['--profile',str(profile),'--rpm','4000','--load','.65','--seconds','3'],'0.9.0')
            assert file.read_bytes()==paths[0].read_bytes();report['other_templates_bit_identical'][str(profile)]=sha(file)
    paths=[]
    for tag,exe,ver in [('v08',OLD,'0.8.0'),('v09',NEW,'0.9.0')]:
        file=OUT/f'lift_pure_{tag}.wav';render(exe,file,CASES['lift']+['--pure'],ver);paths.append(file)
    assert paths[0].read_bytes()==paths[1].read_bytes();report['strict_pure_osc_bit_identical']=True
    # Zero modulation amount also retains the old signal, beyond the switch bypass.
    for tag,enabled in zip(TAGS,[0,1]):render(NEW,OUT/f'zero_{tag}.wav',CASES['mid']+['--irregularity','0'],'0.9.0',['--combustion-variation',str(enabled)])
    assert (OUT/'zero_bypass.wav').read_bytes()==(OUT/'zero_varied.wav').read_bytes();report['zero_amount_bit_identical']=True
    _,report['bed714']=render(NEW,OUT/'drive_714_v09.wav',CASES['drive']+['--channels','12'],'0.9.0',
        ['--stems',str(OUT/'stems/drive_714'),'--scene',str(OUT/'drive_714_scene.json')]);scene_paths(OUT/'drive_714_scene.json',OUT)
    for obj in json.loads((OUT/'drive_714_scene.json').read_text())['objects']:
        assert (OUT/obj['file']).read_bytes()==(OUT/f'stems/drive_varied_{obj["name"]}.wav').read_bytes()
    report['stereo_714_stems_bit_identical']=10
    subprocess.run([sys.executable,str(ROOT/'tools/check_dna_pipeline.py'),'--renderer',str(NEW),'--out',str(OUT/'dna_check')],check=True)
    # Same imported oscillator through engine template, with default feature on/off.
    source=OUT/'dna_check/known_steady_harmonics.dna'
    for tag,exe,ver in [('v08',OLD,'0.8.0'),('v09',NEW,'0.9.0')]:
        render(exe,OUT/f'imported_engine_{tag}.wav',CASES['lift'],ver,['--dna',str(source)])
    assert (OUT/'imported_engine_v08.wav').read_bytes()==(OUT/'imported_engine_v09.wav').read_bytes();report['imported_engine_dna_bit_identical']=True
    device(report)
    report['limits']=['Pressure amplitude/arrival spread and event memory are engineering values, not identified cylinder COV or ignition timing.',
        'Mixed reference envelope variation cannot uniquely separate RPM, microphone motion, intake/exhaust, reflections and recording processing.',
        'Factory V10 only; strict Pure OSC, other four templates and imported DNA retain their existing policy and timing.',
        'The conservative phase-warp frequency margin is not a mathematical proof of alias-free arbitrary FM.',
        'Subjective realism, dominant RPM/load spectrum maps, physical dynamics and calibrated 7.1.4 listening remain incomplete.']
    update_files(report);print(json.dumps(report['device'],indent=2))


if __name__=='__main__':
    if '--device-only' in sys.argv:
        report=json.loads((OUT/'verification.json').read_text());device(report);update_files(report);print(json.dumps(report['device'],indent=2))
    else:main()

"""Verify unchanged legacy renders, new bed source/layout invariants and short muted device takes."""
import argparse
import csv
import json
from pathlib import Path
import shutil
import subprocess
import sys

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True);parser.add_argument('--out',type=Path,required=True)
args=parser.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from drive_evidence_v1.sources import sha

args.out.mkdir(parents=True,exist_ok=False);(args.out/'bin').mkdir();(args.out/'renders').mkdir();(args.out/'device').mkdir()
root=args.workspace/'references/analysis/stereo_bed_v1';before=root/'before';build=repo/'build-stereo-bed-v1'
record=json.loads((root/'build1/report.json').read_text(encoding='utf-8'));assert record['result']=='build_and_41tests_pass'
for name,digest in record['source_sha256'].items():assert sha(repo/name)==digest
old=json.loads((before/'report.json').read_text(encoding='utf-8'))
for name,digest in old['files'].items():assert sha(before/name)==digest
for path in (build/'bin/Release').glob('VslAtlas*.exe'):shutil.copy2(path,args.out/'bin'/path.name)
sources=[Path(__file__),repo/'tools/drive_evidence_v1/sources.py']
for path in sources:
    target=args.out/'exact_sources'/path.relative_to(repo);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
r=dict(schema='vsl.stereo-bed-verification/1',result='running',commands=[],legacy=[],bed=[],device={},exports=[],
       source_sha256={p.relative_to(repo).as_posix():sha(p) for p in sources},
       input_sha256={str(root/'build1/report.json'):sha(root/'build1/report.json'),str(before/'report.json'):sha(before/'report.json')},
       binary_sha256={p.name:sha(p) for p in (args.out/'bin').iterdir()},human_accepted=False,long_run_checked=False,hardware12_checked=False)

def run(command,expected=0):
    result=subprocess.run([str(x) for x in command],cwd=repo,capture_output=True,timeout=120)
    name=f'command_{len(r["commands"]):02}.log';(args.out/name).write_bytes(result.stdout+result.stderr)
    r['commands'].append(dict(argv=[str(x) for x in command],exit_code=result.returncode,log=name,sha256=sha(args.out/name)))
    print(json.dumps(dict(command=Path(command[0]).name,exit_code=result.returncode,log=name)),flush=True)
    assert result.returncode==expected,name
    return result.stdout

probe=args.out/'bin/VslAtlasDrive_probe.exe'
try:
    for case in old['cases']:
        prefix=args.out/'renders'/case['name']
        run([probe,*case['models'][:2],prefix,*case['options']])
        originals=list((before/'renders').glob(case['name']+'_*.wav'))
        assert len(originals)==26
        for path in originals:assert path.read_bytes()==(prefix.parent/path.name).read_bytes(),path.name
        assert (before/'renders'/(case['name']+'_trace.csv')).read_bytes()==prefix.with_name(prefix.name+'_trace.csv').read_bytes()
        r['legacy'].append(dict(name=case['name'],all26_WAV_bytes_equal=True,control_trace_equal=True))
    # Same real model/configuration as each legacy case; only routing flag changes.
    for case in old['cases']:
        prefix=args.out/'renders'/(case['name']+'_bed')
        run([probe,*case['models'][:2],prefix,*case['options'],'--stereo-bed','1'])
        source_names=['dna_raw','dna','dry','event_layer','residual_raw','residual','harmonic_body_raw','harmonic_body','auxiliary',
                      'aux_raw_intake','aux_raw_mechanical','aux_raw_air_left','aux_raw_air_right','aux_raw_road','aux_raw_wind']
        for name in source_names:
            original=before/'renders'/(case['name']+'_'+name+'.wav')
            assert original.read_bytes()==prefix.with_name(prefix.name+'_'+name+'.wav').read_bytes(),name
        assert (before/'renders'/(case['name']+'_trace.csv')).read_bytes()==prefix.with_name(prefix.name+'_trace.csv').read_bytes()
        # Exhaust proxies and complementary BODY must no longer duplicate the bed.
        for source in ['exhaust_left','exhaust_right','body']:
            x,_=sf.read(prefix.with_name(prefix.name+'_'+source+'.wav'),always_2d=True);assert np.count_nonzero(x)==0
        r['bed'].append(dict(name=case['name'],all15_source_WAV_bytes_equal=True,control_trace_equal=True,no_bed_in_exhaust_body_objects=True))
    # Body+residual keep their observed L/R. No events/auxiliary objects; width1,
    # default before-master source =>2/12front samples must agree without upmix.
    case=old['cases'][2];models=case['models'];options=[]
    for model in models:options+=['--residual-anchor',str(repo/'voices/residual_atlas_v1'/(Path(model).stem+'.residual'))]
    outputs={}
    for channels in (2,12):
        prefix=args.out/'renders'/f'E_bed_only_{channels}'
        run([probe,*models,prefix,'--seconds','4','--scenario','fixed','--rpm','7600','--load','.8',
             '--stereo-bed','1','--spatial','1','--channels',channels,'--body-mix','.6','--residual-gain','.35',
             '--gain','.25','--room','.2',*options])
        x,rate=sf.read(prefix.with_name(prefix.name+'_render.wav'),always_2d=True);assert rate==48000
        dry,_=sf.read(prefix.with_name(prefix.name+'_dry.wav'),always_2d=True)
        assert np.array_equal(x[:,:2],dry)
        if channels==12:assert np.count_nonzero(x[:,2:])==0
        outputs[channels]=x
    assert np.array_equal(outputs[2],outputs[12][:,:2])
    x=outputs[2][48000:];mid=(x[:,0]+x[:,1])*.5;side=(x[:,0]-x[:,1])*.5
    r['bed_only']=dict(front2_12_and_direct_exact=True,other10_channels_silent=True,
        side_mid_dB=float(10*np.log10(np.mean(side*side)/np.mean(mid*mid))))
    # Old files still use their frozen matching player; new schema3 must reject them.
    old_take=args.workspace/'baselines/system_status_v1/evidence/device1/device_take.vslrun'
    r['input_sha256'][str(old_take)]=sha(old_take)
    run([before/'bin/VslAtlasTake_render.exe',old_take,args.out/'old_take.wav'])
    run([args.out/'bin/VslAtlasTake_render.exe',old_take,args.out/'rejected_old.wav'],expected=3)
    assert not (args.out/'rejected_old.wav').exists()
    r['old_schema2_player_preserved']=True
    run([args.out/'bin/VslAtlasMonitor_device_verify.exe',args.out/'device','--stereo-bed'])
    for name in ['bench','pedals','stopped','cabin_restart']:
        case=json.loads((args.out/'device'/(name+'.json')).read_text(encoding='utf-8'))
        assert case['healthy'] and case['offline_float_equal'] and case['queue_empty']==0
        r['device'][name]={k:case[k] for k in ['frames','healthy','offline_float_equal','queue_empty','budget_exceeded','render_max_ms']}
    run([args.out/'bin/VslAtlasTake_device_checks.exe',args.out/'bed_take.vslrun','--stereo-bed'])
    take=json.loads((args.out/'bed_take.vslrun.json').read_text(encoding='utf-8'))
    assert take['verified'] and take['record_hash']==take['play_hash']
    with (args.out/'bed_take.vslrun').open('rb') as f:header=f.read(108)
    assert int.from_bytes(header[8:12],'little')==3 and int.from_bytes(header[104:108],'little')==1
    r['take']=take;r['take_schema']=3;r['control_fields']=int.from_bytes(header[76:80],'little')
    assert r['control_fields']==25
    for channels in (2,12):
        result=run([args.out/'bin/VslAtlasTake_render.exe',args.out/'bed_take.vslrun',args.out/f'take_{channels}.wav','--channels',channels])
        item=json.loads(result);assert item['verified'];r['exports'].append(item)
    assert r['exports'][0]['source_hash']==r['exports'][1]['source_hash']
    r.update(result='technical_pass_only',meaning='Legacy bytes/source identity and bed routing function; not naturalness,long-run or physical12speaker qualification')
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:(args.out/'report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')

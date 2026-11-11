"""Audit real exterior anchors and exercise the same C driving atlas with4models."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import types
import zipfile

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True)
parser.add_argument('--anchors',type=Path,required=True)
parser.add_argument('--probe',type=Path,required=True)
parser.add_argument('--out',type=Path,required=True)
args=parser.parse_args()
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from drive_evidence_v1.sources import sha
from drive_evidence_v1.family import follow

repository=Path(__file__).resolve().parents[1]
args.out.mkdir(parents=True,exist_ok=False)
build=json.loads((args.anchors/'build.json').read_text(encoding='utf-8'))
controls=args.workspace/'references/analysis/exterior_clock_v1/warp_controls_v2/verification.json'
control=json.loads(controls.read_text(encoding='utf-8'))
assert control['result']=='pass'
for name,expected in control['source_sha256'].items():assert sha(repository/'tools'/name)==expected
for name,expected in build['source_sha256'].items():assert sha(repository/name)==expected
assert sha(repository/'handoff-build/bin/Release/VslSoundDna_probe.exe')==build['probe_sha256']
models=[];anchor_checks=[]
for row in build['anchors']:
    output=args.anchors/row['name'];model=output/'voice.model'
    assert sha(model)==row['model_sha256'];models.append(model)
    for rendered in row['render']:
        assert sha(output/f"raw_{rendered['pitch']:.1f}.wav")==rendered['sha256']
    assert row['statistics']['observation_frames']>=32
    assert row['original_warp']['source_cutoff_hz']<row['original_warp']['source_min_nyquist_hz']
    heldout=('15','20') if row['phase_polish']['reference_order']==10 else ('3','7')
    for order in heldout:
        measured=row['carrier_diagnostics'][order]
        assert not measured['fitted_reference']
        assert min(measured['after']['coherence'])>.80
    main_bands=('28_120','120_400','400_1200')
    assert max(abs(v) for band in main_bands for v in row['bands'][band]['generated_minus_reference_db'])<3
    anchor_checks.append(dict(name=row['name'],model_sha256=row['model_sha256'],base_hz=row['base_hz'],
        modeled_top_hz=row['modeled_top_hz'],heldout_orders=list(heldout),
        normalized_cycles=row['phase_polish']['normalized_frames']/1024,
        heldout_coherence={order:row['carrier_diagnostics'][order]['after']['coherence'] for order in heldout}))
assert np.all(np.diff([row['base_hz'] for row in build['anchors']])>0)

# Default invocation remains numerically identical to the frozen E tracker;
# only the new caller opts into8..90Hz. No historical analysis is rewritten.
with zipfile.ZipFile(args.workspace/'baselines/drive_evidence_v1/source.zip') as archive:
    previous=types.ModuleType('previous_family')
    exec(compile(archive.read('tools/drive_evidence_v1/family.py'),'frozen_family.py','exec'),previous.__dict__)
hz=np.arange(0,1601.)
times=np.arange(101)*.01
power=np.full((len(hz),len(times)),1e-12)
for multiple in (2,3,5,7):
    power+=np.exp(-.5*((hz[:,None]-multiple*40)/3)**2)
assert follow(hz,times,power,0,1,40)==previous.follow(hz,times,power,0,1,40)
low_power=np.full_like(power,1e-12)
for multiple in (5,10,15,20):low_power+=np.exp(-.5*((hz[:,None]-multiple*10)/2)**2)
low_path=follow(hz,times,low_power,0,1,10,10,(5,15,20),8,(8,90))
assert low_path['status']=='connected_observed_family'
assert max(abs(row['root_hz']-10) for row in low_path['rows'])<.01

report=dict(schema='vsl.exterior-atlas-validation/1',accepted=False,build_sha256=sha(args.anchors/'build.json'),
    warp_control_sha256=sha(controls),anchors=anchor_checks,runs=[],probe_sha256=sha(args.probe),
    old_family_default_bit_equal=True,root_per_rpm_status='Explicit1/120 engineering hypothesis; not A tach telemetry',
    largest_anchor_interval_ratio=max(b['base_hz']/a['base_hz'] for a,b in zip(build['anchors'],build['anchors'][1:])),
    limits=['Only4stationary rear anchors; large10..31.5Hz gap, mixed falling-rev windows and sparse state evidence',
        'Interval telemetry is a bracket test, not proof of measured timbre/load/state coverage',
        'Independent LF/intake/noise layers and native4anchor driving UI are not connected',
        'No human listening acceptance or actual device/speaker validation'])
suffixes=('render','dna_raw','dna','dry','event_layer','exhaust_left','exhaust_right','intake','body',
    'mechanical','air_left','air_right','events','road','wind')
auto_raw=None
for name,scenario,seconds,channels in [('auto','auto',30,2),('auto12','auto',30,12),('neutral','neutral',8,2),('downshift','downshift',18,2)]:
    prefix=args.out/name
    command=[str(args.probe),str(models[0]),str(models[1]),str(prefix)]
    for model in models[2:]:command+=['--anchor',str(model)]
    command+=['--scenario',scenario,'--seconds',str(seconds),'--channels',str(channels),'--root-per-rpm',str(1/120)]
    result=subprocess.run(command,capture_output=True,text=True,check=True,timeout=120)
    meta=json.loads((args.out/(name+'_report.json')).read_text(encoding='utf-8'))
    assert meta['anchor_count']==4 and meta['source_frame']==meta['owner_frame']==seconds*48000
    assert np.array_equal(meta['base_hz'],[row['base_hz'] for row in build['anchors']])
    audio,rate=sf.read(args.out/(name+'_render.wav'),always_2d=True)
    raw,_=sf.read(args.out/(name+'_dna_raw.wav'),always_2d=True)
    dry,_=sf.read(args.out/(name+'_dry.wav'),always_2d=True)
    trace=np.genfromtxt(args.out/(name+'_trace.csv'),delimiter=',',names=True)
    assert rate==48000 and audio.shape==(seconds*48000,channels) and np.isfinite(audio).all()
    assert abs(audio).max()<.95 and not np.array_equal(raw[:48000],raw[-48000:])
    assert len(trace)==seconds*200 and max(trace['upper'])==3 and min(trace['lower'])==0
    if channels==2:assert np.array_equal(audio,dry)
    if name=='auto':auto_raw=raw.copy();auto_trace=trace.copy()
    if name=='auto12':
        assert np.array_equal(raw,auto_raw) and np.array_equal(trace,auto_trace)
        assert np.max(abs(audio[:,8:]))==0
    for layer in ('event_layer','events','body','intake','mechanical','air_left','air_right','road','wind'):
        data,_=sf.read(args.out/f'{name}_{layer}.wav');assert np.max(abs(data))==0
    files={name+'_'+suffix+'.wav':sha(args.out/(name+'_'+suffix+'.wav')) for suffix in suffixes}
    (args.out/(name+'_command.json')).write_text(json.dumps(dict(command=command,stdout=result.stdout,stderr=result.stderr,
        probe_sha256=sha(args.probe),files_sha256=files),ensure_ascii=False,indent=2),encoding='utf-8')
    report['runs'].append(dict(name=name,frames=len(audio),channels=channels,peak=float(abs(audio).max()),
        shifts=meta['shifts'],overruns=meta['overruns'],covered_bracket_fraction=meta['covered_frames']/len(audio),
        process_seconds=meta['process_seconds'],max_block_seconds=meta['max_block_seconds'],
        block_budget_exceedances=meta['block_budget_exceedances'],files_sha256=files))
    print(name,'4anchors passed','peak',float(abs(audio).max()),'bracket fraction',meta['covered_frames']/len(audio),flush=True)

# Backward compatibility: unchanged two-anchor E audio through the generalized
# command parser; compare source and mix to frozen samples over an actual shift.
e_models=[repository/'voices/cabin_anchors_v1'/f'E Cabin {part}.model' for part in ('Lower','Upper')]
command=[str(args.probe),*map(str,e_models),str(args.out/'legacy_E'),'--seconds','8']
subprocess.run(command,check=True,capture_output=True,timeout=90)
for suffix in suffixes:
    current,_=sf.read(args.out/f'legacy_E_{suffix}.wav',always_2d=True)
    frozen,_=sf.read(args.workspace/f'baselines/atlas_drive_v1/evidence/auto_{suffix}.wav',frames=8*48000,always_2d=True)
    assert np.array_equal(current,frozen),suffix
report['two_anchor_frozen_E_first8s_all_stems_bit_equal']=True
report['result']='pass'
report['source_sha256']={str(p.relative_to(repository)).replace('\\','/'):sha(p)
    for p in [Path(__file__),repository/'experiments/atlas_drive_v1/probe.c']}
(args.out/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('Exterior4anchor C driving and frozen2anchor regression passed.')

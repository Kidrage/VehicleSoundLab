"""Compare frozen/current driving buses, complementary LF and layout invariants."""
import argparse
import csv
import json
from pathlib import Path
import subprocess
import sys

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True)
parser.add_argument('--out',type=Path,required=True)
args=parser.parse_args()
repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from scipy import signal
from drive_evidence_v1.sources import sha

args.out.mkdir(parents=True,exist_ok=False)
old_root=args.workspace/'baselines/residual_atlas_v1'
manifest=json.loads((old_root/'manifest.json').read_text(encoding='utf-8'))
hashes={r['path']:r['sha256'] for r in manifest['files']}
old=old_root/'bin/VslAtlasDrive_probe.exe'
assert sha(old)==hashes['bin/VslAtlasDrive_probe.exe']
current=repo/'handoff-build/bin/Release/VslAtlasDrive_probe.exe'
runs=[]
def run(name,bank,extra,legacy=False):
    index=json.loads((repo/'voices'/bank/'index.json').read_text(encoding='utf-8'))
    voices=index['voices']
    for item in voices:
        assert sha(repo/'voices'/bank/item['file'])==item['model_sha256']
    command=[str(old if legacy else current),str(repo/'voices'/bank/voices[0]['file']),
        str(repo/'voices'/bank/voices[1]['file']),str(args.out/name)]
    for item in voices[2:]:command+=['--anchor',str(repo/'voices'/bank/item['file'])]
    for item in voices:command+=['--residual-anchor',str(repo/'voices/residual_atlas_v1'/(item['name']+'.residual'))]
    command+=['--gain','.2','--events','.15','--residual-gain','.4',*extra]
    result=subprocess.run(command,cwd=repo,capture_output=True,text=True,encoding='utf-8',errors='replace')
    (args.out/(name+'_command.json')).write_text(json.dumps(dict(argv=command,returncode=result.returncode,
        stdout=result.stdout,stderr=result.stderr),ensure_ascii=False,indent=2),encoding='utf-8')
    assert result.returncode==0,name
    report=json.loads((args.out/(name+'_report.json')).read_text(encoding='utf-8'))
    assert report['peak']<.95
    runs.append(dict(name=name,bank=bank,binary_sha256=sha(old if legacy else current),**report))
    print(name,result.stdout.strip(),flush=True)
def audio(name,suffix):
    x,rate=sf.read(args.out/f'{name}_{suffix}.wav',always_2d=True)
    assert rate==48000 and np.isfinite(x).all()
    return x
def trace(name):
    with (args.out/(name+'_trace.csv')).open(encoding='utf-8',newline='') as stream:
        return list(csv.DictReader(stream))

scenario=['--scenario','auto','--seconds','16']
run('legacy','exterior_anchors_v1',scenario,True)
run('zero','exterior_anchors_v1',scenario+['--body-mix','0'])
old_suffix=[p.name.removeprefix('legacy_').removesuffix('.wav') for p in sorted(args.out.glob('legacy_*.wav'))]
for suffix in old_suffix:
    assert np.array_equal(audio('legacy',suffix),audio('zero',suffix)),suffix
old_trace,zero_trace=trace('legacy'),trace('zero')
assert len(old_trace)==len(zero_trace)
assert all(all(a[k]==b[k] for k in a) for a,b in zip(old_trace,zero_trace))
assert not np.any(audio('zero','harmonic_body')) and np.any(audio('zero','harmonic_body_raw'))
run('layered','exterior_anchors_v1',scenario+['--body-mix','1'])
run('surround','exterior_anchors_v1',scenario+['--body-mix','1','--channels','12','--room','.25'])
for suffix in ('dna_raw','event_layer','residual_raw','residual'):
    assert np.array_equal(audio('zero',suffix),audio('layered',suffix)),suffix
for suffix in old_suffix+['harmonic_body_raw','harmonic_body']:
    if suffix in ('render','dry'):continue
    assert np.array_equal(audio('layered',suffix),audio('surround',suffix)),suffix
layered_trace=trace('layered')
assert all(all(a[k]==b[k] for k in old_trace[0]) for a,b in zip(old_trace,layered_trace))
assert layered_trace==trace('surround')
body=audio('layered','harmonic_body')
expected_body=body.mean(axis=1)
# Source projection happens before float32 stem capture, so compare rounding.
body_error=float(abs(expected_body-audio('layered','body').ravel()).max())
assert body_error<1e-7 and np.mean(body**2)>1e-9
expected=.2*(audio('layered','dna')+body+audio('layered','residual')+audio('layered','event_layer'))
mix_error=float(abs(expected-audio('layered','dry')).max())
assert mix_error<1e-7
assert np.array_equal(audio('layered','dry'),audio('layered','render'))
assert not np.array_equal(audio('zero','render'),audio('layered','render'))
fixed=['--scenario','fixed','--seconds','6','--rpm','4000','--load','.8','--body-mix','1']
run('fixed','exterior_anchors_v1',fixed)
run('cabin','cabin_anchors_v1',['--scenario','fixed','--seconds','6','--rpm','7600','--load','.8','--body-mix','1'])
raw=audio('fixed','harmonic_body_raw')[2*48000:]
hz,power=signal.welch(raw,48000,nperseg=16384,axis=0)
leakage=float(power[hz>800].sum()/power.sum())
assert leakage<1e-4
envelopes=np.array([[float(r['envelope']),float(r['body_envelope'])] for r in layered_trace])
assert np.any(abs(envelopes[:,0]-envelopes[:,1])>.01)
source_files=[Path(__file__),repo/'handoff/CMakeLists.txt',
    *sorted((repo/'modules/harmonic_body').glob('*')),
    *sorted((repo/'modules/dna_atlas').glob('*.[ch]')),
    *sorted((repo/'modules/atlas_drive').glob('*.[ch]')),
    repo/'experiments/atlas_drive_v1/probe.c',repo/'experiments/harmonic_body_v1/checks.c']
result=dict(schema='vsl.harmonic-body-driving-verification/1',result='pass',human_accepted=False,
    old_binary_manifest_sha256=sha(old_root/'manifest.json'),old_equal_stems=old_suffix,
    old_common_trace_equal=True,raw_source_and_events_unchanged=True,layout_buses_equal=True,
    body_projection_max_float_error=body_error,mix_max_float_error=mix_error,
    stationary_body_power_above800hz_fraction=leakage,runs=runs,
    source_sha256={p.relative_to(repo).as_posix():sha(p) for p in source_files if p.is_file()},
    limits=['LF is a complementary partition of existing oscillators, not a newly isolated engine source',
        'Engineering20/35/180/350Hz mask,1.6 body voicing scale and existing state envelopes',
        'A4/E2 sparse/context-separated anchors; physical sub-bass/state/engine calibration incomplete',
        'Offline timing does not establish real device or listening acceptance'])
(args.out/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(result='pass',old_stems=len(old_suffix),body_error=body_error,mix_error=mix_error,
    leakage=leakage),ensure_ascii=False))

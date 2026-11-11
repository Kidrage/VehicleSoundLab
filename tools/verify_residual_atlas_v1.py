"""Validate six real anchors, zero-bypass driving and identical 2/12-channel sources."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True)
parser.add_argument('--out',type=Path,required=True)
parser.add_argument('--resume',action='store_true',help='Reuse only commands with verified binary and output hashes')
args=parser.parse_args()
repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from scipy import signal
from drive_evidence_v1.sources import sha
from residual_osc_v1.spectrum import matrices,error

args.out.mkdir(parents=True,exist_ok=args.resume)
root=args.workspace/'references/analysis/residual_atlas_v1'
fit=json.loads((root/'fitted/report.json').read_text(encoding='utf-8'))
profile_index=json.loads((repo/'voices/residual_atlas_v1/index.json').read_text(encoding='utf-8'))
assert profile_index['fit_report_sha256']==sha(root/'fitted/report.json')
probe=repo/'handoff-build/bin/Release/VslAtlasDrive_probe.exe'
contexts={}
for context in ('exterior_anchors_v1','cabin_anchors_v1'):
    voices=json.loads((repo/'voices'/context/'index.json').read_text(encoding='utf-8'))['voices']
    for voice in voices:
        assert sha(repo/'voices'/context/voice['file'])==voice['model_sha256']
        residual=next(r for r in profile_index['voices'] if r['name']==voice['name'])
        assert residual['model_sha256']==voice['model_sha256']
        assert sha(repo/'voices/residual_atlas_v1'/residual['file'])==residual['profile_sha256']
    contexts[context]=voices
commands=json.loads((args.out/'commands.json').read_text(encoding='utf-8')) if args.resume and (args.out/'commands.json').exists() else []


def render(name,context,extra,attached=True,binary=probe):
    voices=contexts[context]
    paths=[str(repo/'voices'/context/r['file']) for r in voices]
    command=[str(binary),*paths[:2],str(args.out/name)]
    for path in paths[2:]:command+=['--anchor',path]
    if attached:
        for row in voices:command+=['--residual-anchor',str(repo/'voices/residual_atlas_v1'/(row['name']+'.residual'))]
    command+=extra
    previous=next((r for r in commands if r['name']==name),None)
    if previous:
        assert args.resume and previous['command']==command and previous['binary_sha256']==sha(binary)
        for filename,expected in previous['files_sha256'].items():assert sha(args.out/filename)==expected
        return json.loads((args.out/(name+'_report.json')).read_text(encoding='utf-8'))
    result=subprocess.run(command,check=True,capture_output=True,text=True,timeout=180)
    record=dict(name=name,command=command,binary_sha256=sha(binary),stdout=result.stdout,
        files_sha256={p.name:sha(p) for p in args.out.glob(name+'_*') if p.is_file()})
    commands.append(record)
    (args.out/'commands.json').write_text(json.dumps(commands,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(name,result.stdout.strip(),flush=True)
    return json.loads((args.out/(name+'_report.json')).read_text(encoding='utf-8'))


def audio(name,suffix):
    x,rate=sf.read(args.out/(name+'_'+suffix+'.wav'),always_2d=True)
    assert rate==48000 and np.isfinite(x).all()
    return x


def cloud_matrices(x):
    # Validate model band powers using1.46Hz resolution. The2048-point fit
    # estimator smears a strong adjacent band's carriers across boundaries;
    # that leakage is not the continuous source's in-band variance error.
    kw=dict(fs=48000,nperseg=32768,noverlap=16384,window='hann',detrend=False,scaling='density')
    hz,p=signal.welch(x,axis=0,**kw)
    _,cross=signal.csd(x[:,0],x[:,1],**kw)
    rows=[]
    for low,high in [(1200,1500),(1500,1900),(1900,2400),(2400,3000),
                     (3000,3800),(3800,4800),(4800,6000),(6000,8000)]:
        mask=(hz>=low)&(hz<high);c=complex(cross[mask].sum()*(hz[1]-hz[0]))
        rows.append(dict(hz=[low,high],power=(p[mask].sum(axis=0)*(hz[1]-hz[0])).tolist(),cross=[c.real,c.imag]))
    return rows


endpoints=[]
for n,case in enumerate(fit['cases']):
    name=f'anchor{n}'
    render(name,case['context'],['--scenario','fixed','--seconds','6','--rpm',str(case['base_hz']*120),
        '--load','.8','--gain','.25','--residual-gain','1'])
    # Lifecycle startup initially selects lower anchors. Only measure the fixed
    # endpoint after actual controller/root convergence, not the startup sweep.
    trace=np.genfromtxt(args.out/(name+'_trace.csv'),delimiter=',',names=True)
    assert max(abs(trace['root_hz'][trace['seconds']>=3]-case['base_hz']))<1e-5
    raw=audio(name,'residual_raw')[3*48000:]
    targets=[]
    for row in case['rows']:
        power=row['power'];cross=np.asarray(row['coherence'])*np.sqrt(np.prod(power))
        targets.append(dict(hz=row['hz'],power=power,cross=cross.tolist()))
    coarse=error(targets,matrices(raw))
    measured=error(targets,cloud_matrices(raw))
    active=[r for r,enabled in zip(measured,case['active_bands']) if enabled]
    maximum=max(abs(value) for row in active for value in row['power_delta_db'])
    coherence=max(row['complex_coherence_error'] for row in active)
    assert maximum<.8 and coherence<.1,(name,maximum,coherence)
    endpoints.append(dict(name=case['name'],max_power_error_db=maximum,max_coherence_error=coherence,
        active_bands=case['active_bands'],errors=measured,coarse_window_errors=coarse,
        measurement='Steady endpoint,32768-point Hann;2048-point boundary leakage recorded separately'))

old=args.workspace/'baselines/atlas_realtime_v1/bin/VslAtlasDrive_probe.exe'
assert old.is_file()
fixed=['--scenario','auto','--seconds','16','--gain','.25']
render('legacy','exterior_anchors_v1',fixed,False,old)
render('absent','exterior_anchors_v1',fixed,False)
render('zero','exterior_anchors_v1',fixed+['--residual-gain','0'])
render('layers','exterior_anchors_v1',fixed+['--residual-gain','.6'])
render('surround','exterior_anchors_v1',fixed+['--residual-gain','.6','--channels','12','--room','.25'])
old_suffix=['render','dna_raw','dna','dry','event_layer','exhaust_left','exhaust_right','intake',
            'body','mechanical','air_left','air_right','events','road','wind']
for suffix in old_suffix:
    baseline=audio('legacy',suffix)
    assert np.array_equal(baseline,audio('absent',suffix)),suffix
    assert np.array_equal(baseline,audio('zero',suffix)),suffix
for suffix in ('dna_raw','dna','event_layer'):
    assert np.array_equal(audio('zero',suffix),audio('layers',suffix)),suffix
for suffix in ('dna_raw','dna','residual_raw','residual',*old_suffix[5:]):
    assert np.array_equal(audio('layers',suffix),audio('surround',suffix)),suffix
traces=[(args.out/(name+'_trace.csv')).read_bytes() for name in ('legacy','absent','zero','layers','surround')]
assert all(t==traces[0] for t in traces[1:])
assert not np.array_equal(audio('layers','render'),audio('zero','render'))
assert np.array_equal(audio('layers','render'),audio('layers','dry'))
assert np.any(audio('zero','residual_raw')) and not np.any(audio('zero','residual'))
assert audio('surround','render').shape==(16*48000,12)
report=dict(schema='vsl.residual-atlas-verification/1',result='pass',human_accepted=False,
    endpoints=endpoints,legacy_15_stems_float_equal=True,zero_amount_float_equal=True,
    dna_and_events_unchanged=True,stereo_12channel_sources_equal=True,drive_traces_equal=True,
    fit_sha256=sha(root/'fitted/report.json'),models_index_sha256=sha(repo/'voices/residual_atlas_v1/index.json'),
    probe_sha256=sha(probe),old_probe_sha256=sha(old),commands_sha256=sha(args.out/'commands.json'),
    limits=['Endpoint spectral verification only, not dynamic naturalness or measured RPM/state coverage',
            'No actual multichannel speaker/device test; timing results are offline host measurements'])
(args.out/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k!='endpoints'},ensure_ascii=False))

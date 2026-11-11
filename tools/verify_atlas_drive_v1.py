"""Render and independently inspect the provisional C multi-anchor driving path."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace', type=Path, required=True)
parser.add_argument('--out', type=Path, required=True)
parser.add_argument('--resume', action='store_true', help='Reuse only commands with matching binary/model/output hashes')
args = parser.parse_args()
repository = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(args.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from scipy import signal

def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

models = [repository/'voices/cabin_anchors_v1'/f'E Cabin {name}.model' for name in ('Lower', 'Upper')]
assert [sha(p) for p in models] == [
    'e74e98a6c82f6ce2359a2fded3a30d35f7265a9d7014b7bc356b1533cace4cf9',
    '819a343cd1e232700e21ac4f1d57e7ce817293c66902d812015399325837d5a3']
probe = repository/'handoff-build/bin/Release/VslAtlasDrive_probe.exe'
args.out.mkdir(parents=True, exist_ok=args.resume)
runs = [('auto', 30, 2, 0, 0), ('auto_spatial', 30, 12, 0, 0),
    ('neutral', 8, 2, 0, 0), ('downshift', 18, 2, 0, 0), ('shifts_events', 13, 2, .5, 0),
    ('lower', 6, 2, 0, 60.634271286273396*120),
    ('mid', 6, 2, 0, (60.634271286273396+64.84675603879224)*60),
    ('upper', 6, 2, 0, 64.84675603879224*120)]
report = dict(schema='vsl.atlas-drive-validation/1', accepted=False,
    model_sha256={str(p.relative_to(repository)):sha(p) for p in models},
    probe_sha256=sha(probe), runs=[], limits=[
        'No human acceptance of cabin anchors, interpolation, new driving audio or spatial output',
        'Two narrow high-RPM cabin anchors, not a complete RPM/load/state atlas',
        'E root=RPM/120 is a finite recording-supported hypothesis, not tach telemetry',
        'Only DNA and optional legacy procedural events; no separate cabin LF, intake or air source',
        'Performance from offline host; no waveOut/real-speaker validation in this experiment'])
wave_suffixes=('render','dna_raw','dna','dry','event_layer','exhaust_left','exhaust_right',
    'intake','body','mechanical','air_left','air_right','events','road','wind')
for name, seconds, channels, event_gain, rpm in runs:
    scenario = 'fixed' if rpm else name.split('_')[0]
    prefix = args.out/name
    command = [str(probe), *map(str, models), str(prefix), '--scenario', scenario,
        '--seconds', str(seconds), '--channels', str(channels), '--events', str(event_gain)]
    if rpm:
        command += ['--rpm', str(rpm), '--load', '.8']
    command_path=args.out/(name+'_command.json')
    if args.resume and command_path.exists():
        previous=json.loads(command_path.read_text(encoding='utf-8'))
        assert previous['command']==command and previous['probe_sha256']==sha(probe)
        assert previous['model_sha256']==report['model_sha256']
        for filename,expected in previous['outputs_sha256'].items():
            assert sha(args.out/filename)==expected
    else:
        result = subprocess.run(command, capture_output=True, text=True, check=True, timeout=120)
        command_path.write_text(json.dumps(dict(command=command, probe_sha256=sha(probe),
            model_sha256=report['model_sha256'], stdout=result.stdout, stderr=result.stderr,
            outputs_sha256={p.name:sha(p) for p in args.out.glob(name+'_*') if p.is_file()}),
            ensure_ascii=False, indent=2), encoding='utf-8')
    metadata = json.loads((args.out/(name+'_report.json')).read_text(encoding='utf-8'))
    trace = np.genfromtxt(args.out/(name+'_trace.csv'), delimiter=',', names=True)
    output, rate = sf.read(args.out/(name+'_render.wav'), always_2d=True)
    assert output.shape == (seconds*48000, channels) and rate == 48000 and np.isfinite(output).all()
    assert len(trace) == seconds*200 and np.array_equal(trace['frame'], np.arange(len(trace))*240)
    assert metadata['source_frame'] == metadata['owner_frame'] == len(output)
    assert abs(float(abs(output).max())-metadata['peak']) < 1e-10 and metadata['peak'] < .95
    raw, rate = sf.read(args.out/(name+'_dna_raw.wav'), always_2d=True)
    dna, _ = sf.read(args.out/(name+'_dna.wav'), always_2d=True)
    dry, _ = sf.read(args.out/(name+'_dry.wav'), always_2d=True)
    events, _ = sf.read(args.out/(name+'_event_layer.wav'))
    event_object, _ = sf.read(args.out/(name+'_events.wav'))
    assert np.array_equal(events, event_object)
    left, _ = sf.read(args.out/(name+'_exhaust_left.wav'))
    right, _ = sf.read(args.out/(name+'_exhaust_right.wav'))
    assert raw.shape == dna.shape == dry.shape == (len(output), 2)
    # Captures round separate double computations tofloat32. Propagate their
    # half-ULP bounds, rather than comparing differently rounded sums exactly.
    def half_ulp(x):
        return .5*abs(np.spacing(np.asarray(x,dtype=np.float32)).astype(np.float64))
    routing_error=abs(left-.25*(dna[:,0]+dna[:,1]))
    routing_bound=.25*(half_ulp(dna[:,0])+half_ulp(dna[:,1]))+half_ulp(left)
    assert np.all(routing_error <= routing_bound+1e-14)
    assert np.array_equal(left, right)
    assert np.all(abs(dry-.5*(dna+events[:,None])) <=
        .5*(half_ulp(dna)+half_ulp(events[:,None]))+half_ulp(dry)+1e-14)
    if channels == 2:
        assert np.array_equal(output, dry)
    if not event_gain:
        assert np.max(abs(events)) == 0
    else:
        assert np.max(abs(events)) > .001 and metadata['procedural_hits'] > 0
    # Unconnected layers must contain silence, not a second hidden engine voice.
    for layer in ('intake', 'body', 'mechanical', 'air_left', 'air_right', 'road', 'wind'):
        layer_data, _ = sf.read(args.out/f'{name}_{layer}.wav')
        assert np.max(abs(layer_data)) == 0
    # Texture differs in later time, and original L/R observations survive.
    assert not np.array_equal(raw[:48000], raw[-48000:])
    assert np.max(abs(raw[:,0]-raw[:,1])) > .001
    if name == 'auto':
        auto_raw=raw.copy();auto_trace=trace.copy()
        assert metadata['shifts'] >= 2 and metadata['overruns'] >= 1
        assert np.max(trace['root_hz']) > metadata['base_hz'][0]+2
        assert metadata['below_frames'] > 0 and metadata['covered_frames'] > 0
    elif name == 'auto_spatial':
        assert np.array_equal(raw, auto_raw)
        assert np.array_equal(trace, auto_trace)
        assert np.count_nonzero(np.max(abs(output[:,:8]), axis=0) > 1e-6) >= 3
        assert np.max(abs(output[:,3])) > 1e-6  # Dedicated low-pass LFE.
        # This case requests zero room: height reflection buses remain silent.
        assert np.max(abs(output[:,8:])) == 0
    elif rpm:
        assert abs(trace['root_hz'][-1]-rpm/120) < 1e-6
    bands = {}
    f, p = signal.welch(raw[-3*48000:], fs=48000, nperseg=8192, axis=0)
    for lo, hi in [(28,120),(120,400),(400,1200),(1200,3000),(3000,8000),(8000,14000),(21600,24000)]:
        bands[f'{lo}_{hi}'] = (10*np.log10(np.sum(p[(f>=lo)&(f<hi)], axis=0)*(f[1]-f[0])+1e-30)).tolist()
    row=dict(name=name, frames=len(output), channels=channels, peak=metadata['peak'],
        coverage_frames=[metadata[k] for k in ('below_frames','covered_frames','above_frames')],
        root_hz_range=[float(min(trace['root_hz'])),float(max(trace['root_hz']))],
        operating_states=np.unique(trace['operating']).astype(int).tolist(),
        shifts=metadata['shifts'],overruns=metadata['overruns'],procedural_hits=metadata['procedural_hits'],
        process_seconds=metadata['process_seconds'],max_block_seconds=metadata['max_block_seconds'],
        block_budget_exceedances=metadata['block_budget_exceedances'],
        final3s_band_db= bands,
        files_sha256={name+'_'+suffix+'.wav':sha(args.out/(name+'_'+suffix+'.wav')) for suffix in wave_suffixes})
    report['runs'].append(row)
    print(name, 'passed', 'peak', row['peak'], 'max-block-ms', 1000*row['max_block_seconds'], flush=True)

# Independent numerical audit of the shared cycle shift from original means.
def means(path):
    values = path.read_text(encoding='utf-8').split()
    assert values[:2] == ['VSL_SOUND_DNA', '1']
    harmonics, components = int(values[5]), int(values[6])
    at=8+components
    records=np.array(list(map(float, values[at:]))).reshape(harmonics,4+4*components+1+16)
    return records[:,:4:2]+1j*records[:,1:4:2]
a,b=map(means,models)
offset=json.loads((args.out/'auto_report.json').read_text())['cycle_offsets'][1]
h=np.arange(1,33)[:,None]
def score(x):
    return float(np.real(np.sum(np.conj(a[:32])*b[:32]*np.exp(1j*h*x))))
fitted=score(offset)
assert fitted >= max(score(x) for x in np.linspace(-np.pi,np.pi,2048,endpoint=False))-1e-10
assert np.max(abs(np.angle((b*np.exp(1j*np.arange(1,len(b)+1)[:,None]*offset))[:,1]/
    (b*np.exp(1j*np.arange(1,len(b)+1)[:,None]*offset))[:,0])-np.angle(b[:,1]/b[:,0]))) < 1e-10
report['alignment']=dict(common_lr_offset_radians=offset,unaligned_score=score(0),aligned_score=fitted,
    scope='Arbitrary common cycle origin from low32orders; no physical timing/source claim')
report['source_sha256']={str(p.relative_to(repository)).replace('\\','/'):sha(p)
    for folder in ('modules/dna_atlas','modules/atlas_drive','experiments/atlas_drive_v1')
    for p in (repository/folder).glob('*') if p.is_file()}
report['verifier_sha256']=sha(__file__)
report['result']='pass'
destination=args.out/'verification.json'
if destination.exists():
    previous=destination.read_bytes()
    archived=args.out/('verification_'+hashlib.sha256(previous).hexdigest()[:12]+'.json')
    if not archived.exists():archived.write_bytes(previous)
destination.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('All C render, shared alignment, layer, clock, channel and coverage checks passed.')

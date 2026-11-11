"""Fixed multi-resolution ablation with synthetic and disjoint recording checks."""
from pathlib import Path
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools/python_deps'))
import numpy as np
import soundfile as sf
from osc_research.multires import synthesize, QUOTAS
from osc_research.tracker import synthesize as long_synth, Settings
from osc_research.metrics import measure, compare
from finalize_joint_stereo import read_source

OUT = ROOT/'references/analysis/multires_v1'
PRIOR = ROOT/'references/analysis/joint_stereo_v1'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


def controls():
    sr = 48000
    t = np.arange(2*sr)/sr
    fixed = np.zeros((len(t), 2))
    for f, a, shift, ratio in [(43.37,.18,.2,.8),(337.71,.1,np.pi,1),
                              (1241.26,.05,-1.7,.45),(5301.83,.025,2.1,1.2),(10037.29,.012,0,0)]:
        fixed[:, 0] += a*np.cos(2*np.pi*f*t+.3)
        fixed[:, 1] += a*ratio*np.cos(2*np.pi*f*t+.3+shift)
    moving = np.zeros_like(fixed)
    for f, slope, a, am, shift, ratio in [(230,17,.17,2.1,.9,.8),
            (1500,260,.06,3.3,-1.4,1.1),(6500,-550,.025,4.1,2.2,.65)]:
        phase = 2*np.pi*(f*t+.5*slope*t*t)
        amplitude = a*(.7+.3*np.cos(2*np.pi*am*t))
        moving[:, 0] += amplitude*np.cos(phase)
        moving[:, 1] += amplitude*ratio*np.cos(phase+shift)
    result = {}
    for name, x in [('fixed_stereo', fixed), ('moving_am_fm', moving)]:
        methods = {}
        for label, job in [('long28', lambda: long_synth(x, sr, 64, Settings(lower_hz=28))),
                           ('multi64', lambda: synthesize(x, sr, False)),
                           ('balanced64', lambda: synthesize(x, sr, True))]:
            y, _ = job()
            methods[label] = measure(y, sr, x)
            if name == 'fixed_stereo':
                assert methods[label]['relative_waveform_residual_db'] < -45, (name, label, methods[label])
        if name == 'moving_am_fm':
            assert methods['multi64']['relative_waveform_residual_db'] < methods['long28']['relative_waveform_residual_db']-3
        result[name] = methods
    return result


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    base = json.loads((PRIOR/'results.json').read_text(encoding='utf-8'))
    prior_low = json.loads((PRIOR/'low_band_extension.json').read_text(encoding='utf-8'))
    report = dict(schema='vsl.multi-resolution-osc/1',
        settings=dict(low_window=4096, high_window=2048, hop=256, crossover_hz=[800,1600],
                      upper_hz=14000, lower_hz=28, maximum_shared_tracks=64, balanced_quotas=QUOTAS),
        controls=controls(), prior_results_sha256=sha(PRIOR/'results.json'),
        prior_low_sha256=sha(PRIOR/'low_band_extension.json'),
        scope='All reconstruction fits the same excerpt; fixed synthetic-selected settings checked on disjoint recording sections. No generative RPM/load validation or source separation.',
        processing='Stereo float master slices; no source processing. Two centred transforms, complementary complex-amplitude overlap, common frequency support, independent L/R gains. Balanced mode reserves frequency-band slots and redistributes unused slots. No stochastic or residual waveform playback.',
        limits=['Window blending can mix biased chirp phase estimates.',
                'Frequency quotas trade strong-low-order precision for weak-high-frequency coverage; a lower full-waveform error need not track this tradeoff.',
                'A and B remain separate perspectives; no recording-derived binaural field is applied to 7.1.4.',
                'This is a research follow-up, not a runtime voicing preset.'],
        tools={str(p.relative_to(ROOT)):sha(p) for p in [Path(__file__),ROOT/'tools/osc_research/multires.py',
            ROOT/'tools/osc_research/tracker.py',ROOT/'tools/osc_research/metrics.py']}, cases={})
    print('Controls:',{k:{m:round(v['relative_waveform_residual_db'],2) for m,v in c.items()} for k,c in report['controls'].items()},flush=True)
    for name, case in base['cases'].items():
        x, sr = read_source(case)
        assert sha(ROOT/case['master']) == base['sources'][case['source']]['sha256']
        methods = {}
        for label, balanced in [('multi64',False),('balanced64',True)]:
            y, stats = synthesize(x,sr,balanced)
            metrics = measure(y,sr,x)
            gain = 10**(-23/20)/np.sqrt(np.mean(y[9600:-9600]**2))
            common = case['auditions']['reference']['shared_headroom_gain']
            z = y*gain*common
            assert np.max(abs(z)) < .95
            fade = np.linspace(0,1,240)
            z[:240] *= fade[:,None]
            z[-240:] *= fade[::-1,None]
            path = OUT/f'{name}_{label}_rms_matched.wav'
            sf.write(path,z,sr,subtype='PCM_24')
            methods[label] = dict(metrics=metrics, band_errors=compare(case['reference'],metrics),tracking=stats,
                audition=dict(file=str(path.relative_to(ROOT)),sha256=sha(path),rms_gain=float(gain),shared_headroom_gain=common))
        report['cases'][name] = dict(source=case['source'],source_seconds=case['source_seconds'],
            master=case['master'],master_sha256=base['sources'][case['source']]['sha256'],
            long28=prior_low['cases'][name]['metrics'],methods=methods)
        print(name,{m:round(v['metrics']['relative_waveform_residual_db'],2) for m,v in methods.items()},flush=True)
        (OUT/'results.partial.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    (OUT/'results.json').write_text(json.dumps(report,indent=2),encoding='utf-8')


if __name__ == '__main__':
    main()

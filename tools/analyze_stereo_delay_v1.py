"""Raw stereo observations and known controls; no phase warp or runtime fitting."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True)
parser.add_argument('--out',type=Path,required=True)
args = parser.parse_args()
repo = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from stereo_delay_v1.spectrum import measure,scalar_check
from stereo_delay_v1.fit import fit


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


args.out.mkdir(parents=True,exist_ok=False)
plan_path = repo/'research/stereo_delay_v1_plan.json'
plan = json.loads(plan_path.read_text(encoding='utf-8'))
catalog_path = args.workspace/'references/segments_v1.json'
catalog = json.loads(catalog_path.read_text(encoding='utf-8'))
sources = [Path(__file__),plan_path,*sorted((repo/'tools/stereo_delay_v1').glob('*.py'))]
for path in sources:
    target = args.out/'exact_sources'/path.relative_to(repo)
    target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
report = dict(schema='vsl.stereo-phase-slope-analysis/1',result='running',
    plan_sha256=sha(plan_path),catalog_sha256=sha(catalog_path),
    source_sha256={p.relative_to(repo).as_posix():sha(p) for p in sources},numpy_version=np.__version__)
(args.out/'metadata.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
observations,controls = [],[]
try:
    for seed in (23117,61927,8121907):
        rng = np.random.default_rng(seed)
        shared,independent = rng.normal(size=(2,20*48000))
        frequencies = np.fft.rfftfreq(len(shared),1/48000)
        transform = np.fft.rfft(shared)
        for name,delay,rho in (('mono',0,1),('positive',.00045,.9),('negative',-.00065,.9),('independent',0,0)):
            shifted = np.fft.irfft(transform*np.exp(-2j*np.pi*frequencies*delay),n=len(shared))
            audio = np.column_stack((shared,.7*(rho*shifted+np.sqrt(1-rho*rho)*independent)))
            data = measure(audio,48000,plan['size'],plan['hop'],plan['bands'])
            rows = fit(data,plan['bands'],plan)
            if rho>=.9:
                assert max(abs(r['delay_seconds']-delay) for r in rows)<=plan['known_delay_error_seconds'],(seed,name,rows)
            if delay:
                assert min(r['test_rmse_reduction_fraction'] for r in rows)>=plan['known_delay_minimum_rmse_reduction_fraction']
            if not rho:
                assert not any(r['train_phase_qualified'] for r in rows)
            controls.append(dict(seed=seed,name=name,delay_seconds=delay,coherence=rho,bands=rows))
        print('known seed',seed,'pass',flush=True)
    checked = {}
    for case in plan['cases']:
        segment = catalog['segments'][case['segment']]
        assert case['use'] in segment['allowed_uses']
        assert segment['seconds'][0]<=case['seconds'][0]<case['seconds'][1]<=segment['seconds'][1]
        identity = segment['source'];source = catalog['sources'][identity]
        if identity not in checked:
            for key in ('raw','master'):
                assert sha(args.workspace/source[key])==source[key+'_sha256'],(identity,key)
            checked[identity] = {k:source[k] for k in ('raw','master','raw_sha256','master_sha256')}
        with sf.SoundFile(args.workspace/source['master']) as stream:
            assert stream.samplerate==48000 and stream.channels==2 and stream.subtype=='FLOAT'
            start,end = [round(t*48000) for t in case['seconds']]
            stream.seek(start);audio = stream.read(end-start,dtype='float64',always_2d=True)
        assert np.isfinite(audio).all()
        data = measure(audio,48000,plan['size'],plan['hop'],plan['bands'])
        oracle_error = scalar_check(audio,data,48000,plan['size'],plan['hop'])
        assert oracle_error<1e-10,(case['name'],oracle_error)
        rows = fit(data,plan['bands'],plan)
        np.savez_compressed(args.out/(case['name']+'_observations.npz'),**data)
        record = dict(case=case,source=identity,perspective=segment['perspective'],
            source_frame_bounds=[start,end],blocks=len(data['left']),windows_per_block=data['windows_per_block'],
            scalar_dft_max_relative_error=oracle_error,bands=rows)
        observations.append(record)
        print(json.dumps(dict(case=case['name'],qualified=sum(r['predictive_gate_passed'] for r in rows),
            delay_ms=[round(1000*r['delay_seconds'],3) for r in rows],
            reduction=[round(100*r['test_rmse_reduction_fraction'],1) for r in rows])),flush=True)
    report.update(result='pass',controls=controls,observations=observations,sources=checked,
        runtime_changed=False,models_changed=False,human_accepted=False,
        limits=['Mixed raw L/R recording transfer observations, not physical source separation or crank/ECU timing',
            'Nonoverlapping time blocks are disjoint samples, not independent recordings or stationary-load proof',
            'Frame windows overlap inside each block; no independent-frame significance claim',
            'Delay plus complex scalar is an approximation; a passing band is not a whole-cabin/source model',
            'A exterior, B/E cabins and D dyno remain separate; no exterior width inferred from cabin binaural',
            'No synthesized timbre/7.1.4 listening or new state-map acceptance'])
except Exception as exc:
    report.update(result='failed',error=repr(exc),controls=controls,observations=observations)
    raise
finally:
    (args.out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

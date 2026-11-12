"""Density-only C renders, independent oracle/stereo controls and alternating timing."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True)
parser.add_argument('--out',type=Path,required=True)
parser.add_argument('--build-evidence',type=Path,required=True)
parser.add_argument('--probe',type=Path,required=True)
args=parser.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from drive_evidence_v1.sources import sha
from residual_dense_v1.oracle import read,counts,render as oracle
from residual_dense_v1.envelope import measure as envelope
from residual_osc_v1.spectrum import matrices,error,BANDS
from line_density_v1.measure import measure as concentration

args.out.mkdir(parents=True,exist_ok=False)
plan_path=repo/'research/residual_dense_v1_plan.json';plan=json.loads(plan_path.read_text(encoding='utf-8'))
concentration_plan=json.loads((repo/'research/line_density_v1_plan.json').read_text(encoding='utf-8'))
paths=[Path(__file__),plan_path,repo/'research/line_density_v1_plan.json',repo/'tools/drive_evidence_v1/sources.py',
    repo/'tools/residual_osc_v1/spectrum.py',repo/'tools/line_density_v1/measure.py',
    *sorted((repo/'tools/residual_dense_v1').glob('*.py')),
    *[p for name in ('modules/residual_dense','modules/sound_residual','experiments/residual_dense_v1') for p in (repo/name).glob('*') if p.is_file()]]
for path in paths:
    target=args.out/'exact_sources'/path.relative_to(repo);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
r=dict(schema='vsl.residual-dense-run/1',result='running',trials=[],known_controls=[],benchmarks=[],commands=[],input_sha256={},
    source_sha256={p.relative_to(repo).as_posix():sha(p) for p in paths},
    base_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip())
(args.out/'metadata.json').write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8',newline='\n')


def bound(root,name):
    manifest=root/'manifest.json'
    expected=next(row['sha256'] for row in json.loads(manifest.read_text(encoding='utf-8'))['files'] if row['path']==name)
    assert sha(root/name)==expected,name
    r['input_sha256'][str(root/name)]=expected;r['input_sha256'][str(manifest)]=sha(manifest)
    return root/name


def invoke(profile,out,seconds,seed,peak,block=512):
    command=[str(args.probe),str(profile),str(out),str(seconds),'1','1',str(seed),str(peak),str(block)]
    completed=subprocess.run(command,capture_output=True,text=True,timeout=180)
    record=dict(command=command,exit_code=completed.returncode,stdout=completed.stdout,stderr=completed.stderr)
    r['commands'].append(record);completed.check_returncode()
    return json.loads(completed.stdout)


try:
    build=json.loads((args.build_evidence/'report.json').read_text(encoding='utf-8'))
    assert build['result']=='pass' and sha(args.probe)==build['binaries'][str(args.probe)]
    for name,digest in build['source_sha256'].items():assert sha(repo/name)==digest,name
    r['input_sha256'][str(args.build_evidence/'report.json')]=sha(args.build_evidence/'report.json')
    r['input_sha256'][str(args.probe)]=sha(args.probe)
    prior=args.workspace/'baselines/line_density_v1'
    profile=repo/plan['candidate'];moments=read(profile)
    r['input_sha256'][str(profile)]=sha(profile)
    dna,rate=sf.read(bound(prior,'evidence/render1/raw/density_50_dna.wav'),always_2d=True)
    low,low_rate=sf.read(bound(args.workspace/'baselines/coherent_low_v1','evidence/raw/measured.wav'),always_2d=True)
    reference,ref_rate=sf.read(bound(args.workspace/'baselines/residual_motion_v1','evidence/fit1/reference.wav'),always_2d=True)
    assert rate==low_rate==ref_rate==48000 and len(dna)==len(low)==768000
    base=dna+1.6658265329883064*low
    target=matrices(reference);warm=plan['warmup_frames'];raw=args.out/'raw';raw.mkdir()
    known_rows=[]
    for i,(lo,hi) in enumerate(BANDS):known_rows.append([lo,hi,.0007*(i+1),.0011*(i+1),.6,.2])
    known_profile=args.out/'known_stereo.residual'
    known_profile.write_text('VSL_SOUND_RESIDUAL 1 48000 8 32\n'+'\n'.join(' '.join(str(v) for v in row) for row in known_rows)+'\n',encoding='ascii',newline='\n')
    known_target=[dict(hz=row[:2],power=row[2:4],cross=[v*np.sqrt(row[2]*row[3]) for v in row[4:6]]) for row in known_rows]
    for peak in plan['peaks']:
        known_path=raw/f'known_{peak}.wav'
        timing=invoke(known_profile,known_path,plan['seconds'],plan['review_seed'],peak)
        audio,rate=sf.read(known_path,always_2d=True);assert rate==48000
        expected=oracle(np.array(known_rows),counts(np.array(known_rows),peak),plan['review_seed'],2048)
        direct_error=float(np.max(abs(audio[:len(expected)]-expected)))
        assert direct_error<plan['tolerances']['direct_sum_maximum_FS_error'],direct_error
        errors=error(known_target,matrices(audio[warm:]))
        power_error=max(abs(v) for row in errors for v in row['power_delta_db'])
        correlation_error=max(row['complex_coherence_error'] for row in errors)
        assert power_error<plan['tolerances']['known_power_error_db'],(peak,power_error)
        assert correlation_error<plan['tolerances']['known_complex_coherence_error'],(peak,correlation_error)
        r['known_controls'].append(dict(peak=peak,timing=timing,direct_error_FS=direct_error,
            maximum_power_error_db=power_error,maximum_complex_coherence_error=correlation_error))
        for seed in plan['seeds']:
            cloud_path=raw/f'cloud_{peak}_{seed}.wav';timing=invoke(profile,cloud_path,plan['seconds'],seed,peak)
            cloud,rate=sf.read(cloud_path,always_2d=True);assert rate==48000 and len(cloud)==len(base) and np.isfinite(cloud).all()
            mixed=base+cloud
            if peak==32:
                old_cloud,_=sf.read(bound(prior,f'evidence/render1/raw/density_50_{seed}_cloud.wav'),always_2d=True)
                assert np.array_equal(cloud,old_cloud)
            mix_path=raw/f'mix_{peak}_{seed}.wav';sf.write(mix_path,mixed,48000,subtype='FLOAT')
            decoded,_=sf.read(mix_path,always_2d=True)
            if peak==32:
                old_mix,_=sf.read(bound(prior,f'evidence/render1/raw/density_50_{seed}_mix.wav'),always_2d=True)
                assert np.array_equal(decoded,old_mix)
            errors=error(target,matrices(decoded[warm:]))
            power_error=max(abs(v) for row in errors for v in row['power_delta_db'])
            correlation_error=max(row['complex_coherence_error'] for row in errors)
            line_rows=[]
            for cycles in (8,16):
                observed,_=concentration(decoded[warm:warm+len(reference)],concentration_plan,cycles)
                line_rows.append(observed)
            r['trials'].append(dict(peak=peak,seed=seed,timing=timing,cloud_sha256=sha(cloud_path),mix_sha256=sha(mix_path),
                baseline32_samples_exact=peak==32,maximum_power_error_db=power_error,maximum_complex_coherence_error=correlation_error,
                power_gate=power_error<plan['tolerances']['mixed_band_power_error_db'],
                coherence_gate=correlation_error<plan['tolerances']['mixed_complex_coherence_error'],concentration=line_rows,
                cloud_envelope=envelope(cloud[warm:],BANDS),mix_envelope=envelope(decoded[warm:],BANDS)))
        print(json.dumps(dict(peak=peak,counts=timing['counts'],carriers=timing['carriers'],
            powers=[x['maximum_power_error_db'] for x in r['trials'] if x['peak']==peak],
            high_concentration=[x['concentration'][1]['rows'][0]['concentration_LR'][-1][0] for x in r['trials'] if x['peak']==peak])),flush=True)
    for block in plan['benchmark_blocks']:
        for round_index,order in enumerate(plan['benchmark_orders']):
            for peak in order:
                timing=invoke(profile,'-',plan['benchmark_seconds'],plan['review_seed'],peak,block)
                r['benchmarks'].append(dict(round=round_index,**timing))
            print(json.dumps(dict(bench_block=block,round=round_index,order=order)),flush=True)
    passed=all(x['power_gate'] and x['coherence_gate'] for x in r['trials'])
    r.update(result='technical_pass_only' if passed else 'not_passed',density_qualified=passed,
        prior436_C_sources_unchanged=build['prior436_C_sources_unchanged'],driver_changes=False,old_binaries_rebuilt=False,human_accepted=False,
        limits=[plan['scope'],'The model and frequency stratification are fixed across densities; finite seeded phases/beat patterns differ, not paired independent physical observations',
            'Profile moments are the same prior50percent engineering candidate, not refitted per density',
            'Known stereo controls verify spectral moments, not spatial listening or actual7.1.4',
            'Carrier count may trade concentration for temporal lattice beating; neither metric establishes naturalness',
            'No default driving/take/spatial adapter or new host is attached'])
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:(args.out/'report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(result=r['result'],trials=len(r['trials']),benchmarks=len(r['benchmarks']))),flush=True)

"""Check movable local line concentration before bounded spectral-density trials."""
import argparse
import csv
import json
from pathlib import Path
import shutil
import subprocess
import sys

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True)
parser.add_argument('--out',type=Path,required=True)
args=parser.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from drive_evidence_v1.sources import sha
from line_density_v1.measure import measure
from line_density_v1.controls import cases

args.out.mkdir(parents=True,exist_ok=False)
plan_path=repo/'research/line_density_v1_plan.json'
plan=json.loads(plan_path.read_text(encoding='utf-8'))
paths=[Path(__file__),plan_path,repo/'tools/drive_evidence_v1/sources.py',*sorted((repo/'tools/line_density_v1').glob('*.py'))]
for p in paths:
    target=args.out/'exact_sources'/p.relative_to(repo);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target)
r=dict(schema='vsl.line-density-analysis/1',result='running',observations=[],controls=[],input_sha256={},
    source_sha256={p.relative_to(repo).as_posix():sha(p) for p in paths},
    base_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip())
(args.out/'metadata.json').write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8',newline='\n')


def bound(root,name):
    manifest=root/'manifest.json'
    expected=next(row['sha256'] for row in json.loads(manifest.read_text(encoding='utf-8'))['files'] if row['path']==name)
    assert sha(root/name)==expected,name
    r['input_sha256'][str(root/name)]=expected;r['input_sha256'][str(manifest)]=sha(manifest)
    return root/name


def observe(name,audio):
    rows=[];arrays={}
    for cycles in plan['cycles']:
        row,data=measure(audio,plan,cycles)
        assert row['parseval_relative_error']<plan['tolerances']['parseval_relative']
        assert row['direct_DFT_relative_error']<plan['tolerances']['direct_DFT_relative'],(name,cycles,row['direct_DFT_relative_error'])
        rows.append(row);arrays.update({str(cycles)+'_'+k:v for k,v in data.items()})
    path=args.out/(name+'.npz');np.savez_compressed(path,**arrays)
    r['observations'].append(dict(name=name,configurations=rows,arrays_sha256=sha(path)))
    print(json.dumps(dict(name=name,concentration=[dict(cycles=row['cycles'],
        bands_L=[round(v[0],4) for v in row['rows'][0]['concentration_LR']]) for row in rows])),flush=True)


try:
    prior=args.workspace/'baselines/residual_motion_v1'
    reference,rate=sf.read(bound(prior,'evidence/fit1/reference.wav'),always_2d=True)
    base,other_rate=sf.read(bound(prior,'evidence/fit1/accepted_pair.wav'),always_2d=True)
    assert rate==other_rate==48000 and len(reference)==58424
    texture=args.workspace/'baselines/temporal_texture_v1'
    archive=np.load(bound(texture,'evidence/magnitude1/candidate_moments.npz'))
    known=cases(archive['rms'],archive['fixed_phase'],len(reference),plan)
    for name,audio in known:observe(name,audio)
    for cycles in plan['cycles']:
        original,data=measure(known[3][1],plan,cycles)
        gain,_=measure(known[3][1]*.31,plan,cycles)
        swap,swapped=measure(known[3][1][:,::-1],plan,cycles)
        error=max(float(np.max(abs(np.array(a['concentration_LR'])-np.array(b['concentration_LR'])))) for a,b in zip(original['rows'],gain['rows']))
        assert error<plan['tolerances']['gain_invariance']
        for key in ('cell_power','band_power','moving_3','moving_5','fixed_3','fixed_5'):
            assert np.array_equal(data[key][:,:,::-1],swapped[key]),key
        r['controls'].append(dict(cycles=cycles,gain_invariance_error=error,channel_swap_exact=True))
    observe('fixed_A_reference',reference)
    for seconds in plan['candidate_block_starts_seconds']:
        at=round(seconds*48000);observe('accepted_C_'+str(seconds),base[at:at+len(reference)])
    trial_report=json.loads(bound(texture,'evidence/magnitude1/report.json').read_text(encoding='utf-8'))
    for amount in (.5,1.):
        trial=next(row for row in trial_report['trials'] if row['seed']==78283 and row['amount']==amount)
        audio,rate=sf.read(bound(texture,'evidence/magnitude1/'+trial['name']+'.wav'),always_2d=True)
        assert rate==48000
        observe('magnitude_'+str(amount),audio[24000:24000+len(reference)])
    def primary(name,cycles):
        ob=next(row for row in r['observations'] if row['name']==name)
        config=next(row for row in ob['configurations'] if row['cycles']==cycles)
        return np.array(config['rows'][0]['concentration_LR'])
    pure_min=min(float(primary(name,cycles).min()) for name in ('known_fixed_OSC','known_detuned_OSC') for cycles in plan['cycles'])
    noise_max=max(float(primary('known_stationary_noise',cycles).max()) for cycles in plan['cycles'])
    control_gate=pure_min>=plan['tolerances']['pure_tone_minimum_concentration'] and noise_max<=plan['tolerances']['noise_maximum_concentration']
    gap_rows=[];eligible=control_gate;gate=plan['experimental_render_gate']
    for cycles in plan['cycles']:
        average=np.mean([primary('accepted_C_'+str(t),cycles) for t in plan['candidate_block_starts_seconds']],axis=0)
        gap=average-primary('fixed_A_reference',cycles)
        qualifying=np.all(gap>=gate['minimum_concentration_gap'],axis=1)
        count=int(np.sum(qualifying[gate['high_band_indices']]))
        eligible=eligible and count>=gate['minimum_bands_per_window']
        gap_rows.append(dict(cycles=cycles,C_minus_reference_LR=gap.tolist(),qualifying_high_bands=count))
    r['diagnostic_gate']=dict(pure_minimum_concentration=pure_min,stationary_noise_maximum_concentration=noise_max,
        controls_qualified=control_gate,gaps=gap_rows,separate_experimental_C_render_eligible=bool(eligible))
    with (repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig',newline='') as f:index=list(csv.DictReader(f))
    assert len(index)==436
    for row in index:assert sha(repo/row['文件'])==row['SHA-256'],row['文件']
    accepted=json.loads((repo/'research/coherent_low_v1_acceptance.json').read_text(encoding='utf-8'))
    assert sha(repo/accepted['model'])==accepted['model_sha256']
    assert sha(repo/'voices/dna_bank_v1/V10 Exterior.model')==accepted['dna_model_sha256']
    r.update(result='diagnostics_completed',c_h_count=len(index),c_index_sha256=sha(repo/'handoff/C文件索引.csv'),
        runtime_changes=False,new_fit=False,human_accepted=False,accepted_models_unchanged=True,
        limits=[plan['scope'],'Movable-support concentration is not an oscillator/noise power fraction or a realism score',
            'Finite-window chirps/AM can spread pure harmonic energy even when the local peak can translate',
            'Different native grids/support widths have different stationary-noise baselines',
            'No real intrawindow chirp or source/recording contribution is identified here',
            'The experimental gate only authorizes a bounded separate engineering trial, not a physical separation recipe'])
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:(args.out/'report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(result=r['result'],gate=r['diagnostic_gate'])),flush=True)

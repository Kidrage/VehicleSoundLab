"""Fit source resonators and a fixed energy budget around actual unchanged C DNA."""
import argparse,csv,json,shutil,subprocess,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from scipy.optimize import nnls
from drive_evidence_v1.sources import sha
from harmonic_magnitude_v1.legacy import parse,render
from sustain_osc_v1.profile import export
from line_density_v1.profiles import scale
from residual_osc_v1.spectrum import matrices
from resonant_detail_v1.envelope import from_diagnostic
from resonant_detail_v1.filters import fit
from resonant_detail_v1.controls import run

a.out.mkdir(parents=True,exist_ok=False)
plan=json.loads((repo/'research/resonant_detail_v1_plan.json').read_text(encoding='utf-8'))
r=dict(schema='vsl.resonant-detail-fit/1',result='running',plan=plan,input_sha256={},trials=[],source_sha256={})
try:
    paths=[Path(__file__),repo/'research/resonant_detail_v1_plan.json',repo/'tools/harmonic_magnitude_v1/legacy.py',
        repo/'tools/sustain_osc_v1/profile.py',repo/'tools/sustain_osc_v1/oracle.py',repo/'tools/line_density_v1/profiles.py',
        repo/'tools/residual_osc_v1/spectrum.py',*sorted((repo/'tools/resonant_detail_v1').glob('*.py'))]
    for path in paths:
        target=a.out/'exact_sources'/path.relative_to(repo);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
        r['source_sha256'][path.relative_to(repo).as_posix()]=sha(path)
    r['controls']=run(plan)
    def frozen(folder,name):
        root=a.workspace/'baselines'/folder;manifest=json.loads((root/'manifest.json').read_text(encoding='utf-8'))
        expected=next(v['sha256'] for v in manifest['files'] if v['path']==name)
        path=root/name;assert sha(path)==expected;r['input_sha256'][str(path)]=expected
        x,rate=sf.read(path,always_2d=True);assert rate==48000;return x
    reference=frozen('residual_motion_v1','evidence/fit1/reference.wav')
    original=frozen('coherent_low_v1','evidence/raw/dna.wav')[:384000]
    low=frozen('coherent_low_v1','evidence/raw/measured.wav')[:384000]
    source=repo/'voices/dna_bank_v1/V10 Exterior.model';r['input_sha256'][str(source)]=sha(source)
    accepted=json.loads((repo/'research/coherent_low_v1_acceptance.json').read_text(encoding='utf-8'))
    assert sha(source)==accepted['dna_model_sha256']
    diagnostic=repo/'research/dna_texture_v2_summary.json';r['input_sha256'][str(diagnostic)]=sha(diagnostic)
    envelopes=from_diagnostic(json.loads(diagnostic.read_text(encoding='utf-8')),plan['bands_hz'])
    models=fit(reference,plan,envelopes)
    matrix=np.array([m['theoretical_band_power'] for m in models]).T
    target=np.array([v['power'] for v in matrices(reference)])
    ratios=np.sqrt(target[:,1]/target[:,0])
    exe=repo/'build-phase-texture-c-v1/bin/Release/VslSoundDna_probe.exe'
    assert exe.exists();r['input_sha256'][str(exe)]=sha(exe)
    base_model=parse(source);warm=plan['review_crop_frames'][0]
    for amount in [0,*plan['replacement_amounts']]:
        label=f'replace_{round(amount*100):02}';candidate,gain=scale(base_model,amount,plan['harmonic_transition_hz'])
        file=a.out/(label+'.model');export(file,candidate)
        command=list(map(str,[exe,file,a.out/(label+'_dna.wav'),plan['seconds'],1,1,1]))
        done=subprocess.run(command,cwd=repo,capture_output=True,timeout=60)
        (a.out/(label+'_C.log')).write_bytes(done.stdout+done.stderr);assert done.returncode==0
        dna,rate=sf.read(a.out/(label+'_dna.wav'),always_2d=True);assert rate==48000
        if amount==0:assert np.array_equal(dna,original)
        _,removed,_=render(base_model,4096,48271,1-gain)
        error=float(max(abs(original[:len(removed)]-dna[:len(removed)]-removed).ravel()))
        assert error<plan['checks']['C_subtraction_maximum_FS_error'],error
        baseline=dna+low*accepted['low_scale']
        current=np.array([v['power'] for v in matrices(baseline[warm:])])
        debt=target[:,0]-current[:,0]
        # Nonnegative fixed band gains; report unfillable negative debt. No
        # per-seed or per-file normalization after generating a waveform.
        weights=1/np.maximum(target[:,0],1e-20)
        power,residual=nnls(matrix*weights[:,None],np.maximum(debt,0)*weights)
        predicted=current[:,0]+matrix@power
        if amount==0:power[:]=0;predicted=current[:,0]
        trial=dict(amount=amount,label=label,DNA_model_sha256=sha(file),DNA_stem_sha256=sha(a.out/(label+'_dna.wav')),
            C_command=command,C_subtraction_error_FS=error,noise_amplitude_gain=np.sqrt(power).tolist(),
            negative_debt_bands=np.flatnonzero(debt<0).tolist(),predicted_power_error_db=(10*np.log10(predicted/target[:,0])).tolist())
        r['trials'].append(trial)
    with (repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig') as f:index=list(csv.DictReader(f))
    assert len(index)==478
    for row in index:assert sha(repo/row['文件'])==row['SHA-256']
    profile=dict(schema='vsl.resonant-detail-model/1',plan=plan,filters=models,stereo_R_over_L=ratios.tolist(),
                 trials=r['trials'],source_trajectory_stored=False,room_model=False,physical_modes_identified=False)
    (a.out/'detail_model.json').write_text(json.dumps(profile,indent=2)+'\n',encoding='utf-8',newline='\n')
    r.update(result='fit_and_known_controls_pass',model_sha256=sha(a.out/'detail_model.json'),C_H_unchanged=478,
             low_scale=accepted['low_scale'],source_reference_frames=len(reference),no_native_or_listening_acceptance=True)
    print(json.dumps(dict(result=r['result'],maximum_pole_radius=max(v['pole_radius'] for v in models),
         expected_error_db=[v['predicted_power_error_db'] for v in r['trials']],controls=r['controls'])),flush=True)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:(a.out/'report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')

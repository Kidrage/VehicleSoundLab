"""Budget a midrange-preserving candidate using the unchanged v1 resonators."""
import argparse,csv,json,shutil,subprocess,sys
from pathlib import Path

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--out',type=Path,required=True)
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

a.out.mkdir(parents=True,exist_ok=False)
r=dict(schema='vsl.resonant-detail-fit/2',result='running',input_sha256={},source_sha256={})
try:
    def read(path):
        r['input_sha256'][str(path)]=sha(path)
        return json.loads(path.read_text(encoding='utf-8'))
    plan=read(repo/'research/resonant_detail_v2_plan.json')
    feedback=read(repo/'research/resonant_detail_v1_listening.json')
    assert feedback['result']=='retain_35_as_working_candidate_reject_70'
    oldroot=a.workspace/'references/analysis/resonant_detail_v1'
    oldfit=read(oldroot/'fit1/report.json');oldmodel=read(oldroot/'fit1/detail_model.json')
    assert oldfit['result']=='fit_and_known_controls_pass'
    assert sha(oldroot/'fit1/detail_model.json')==oldfit['model_sha256']
    for name,digest in oldfit['source_sha256'].items():assert sha(repo/name)==digest,name
    for name,digest in oldfit['input_sha256'].items():assert sha(Path(name))==digest,name
    paths=[Path(__file__),repo/'tools/line_density_v1/profiles.py',
        repo/'tools/harmonic_magnitude_v1/legacy.py',repo/'tools/sustain_osc_v1/profile.py',
        repo/'tools/sustain_osc_v1/oracle.py',repo/'tools/residual_osc_v1/spectrum.py',
        repo/'tools/drive_evidence_v1/sources.py']
    for path in paths:
        target=a.out/'exact_sources'/path.relative_to(repo)
        target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
        r['source_sha256'][path.relative_to(repo).as_posix()]=sha(path)
    accepted=read(repo/'research/coherent_low_v1_acceptance.json')
    source=repo/'voices/dna_bank_v1/V10 Exterior.model'
    assert sha(source)==accepted['dna_model_sha256']
    r['input_sha256'][str(source)]=sha(source)
    reference_path=a.workspace/'baselines/residual_motion_v1/evidence/fit1/reference.wav'
    low_path=a.workspace/'baselines/coherent_low_v1/evidence/raw/measured.wav'
    original_path=oldroot/'fit1/replace_00_dna.wav'
    for path in (reference_path,low_path,original_path):r['input_sha256'][str(path)]=sha(path)
    assert sha(original_path)==oldmodel['trials'][0]['DNA_stem_sha256']
    reference,rate=sf.read(reference_path,always_2d=True);assert rate==48000
    low,rate=sf.read(low_path,always_2d=True);assert rate==48000
    original,rate=sf.read(original_path,always_2d=True);assert rate==48000
    frames=plan['seconds']*rate;assert len(original)==frames
    base=parse(source)
    candidate,gain=scale(base,plan['replacement_maximum'],plan['harmonic_transition_hz'])
    hz=np.arange(1,len(gain)+1)*rate/1024
    # Independent scalar mask, including boundaries and the half-transition.
    def scalar_gain(f):
        if f<=3000:return 1.
        if f>=6000:return np.sqrt(.65)
        u=(f-3000)/3000
        return np.sqrt(1-.35*u*u*(3-2*u))
    mask_error=float(max(abs(gain-np.array([scalar_gain(f) for f in hz]))))
    assert mask_error<1e-14
    assert scalar_gain(3000)==1 and abs(scalar_gain(4500)**2-.825)<1e-14
    for name in ('mean','basis','root'):
        assert np.array_equal(base[name][hz<=3000],candidate[name][hz<=3000])
    model_path=a.out/'protected.model';export(model_path,candidate)
    exe=repo/'build-phase-texture-c-v1/bin/Release/VslSoundDna_probe.exe'
    r['input_sha256'][str(exe)]=sha(exe)
    command=list(map(str,[exe,model_path,a.out/'protected_dna.wav',plan['seconds'],1,1,1]))
    done=subprocess.run(command,cwd=repo,capture_output=True,timeout=60)
    (a.out/'C.log').write_bytes(done.stdout+done.stderr);assert done.returncode==0
    dna,rate=sf.read(a.out/'protected_dna.wav',always_2d=True);assert rate==48000
    _,removed,_=render(base,4096,plan['DNA_seed'],1-gain)
    oracle_error=float(abs(original[:len(removed)]-dna[:len(removed)]-removed).max())
    assert oracle_error<plan['checks']['C_subtraction_maximum_FS_error']
    baseline=dna+low[:frames]*accepted['low_scale']
    target=np.array([v['power'] for v in matrices(reference)])
    current=np.array([v['power'] for v in matrices(baseline[plan['crop_start_frames']:])])
    matrix=np.array([v['theoretical_band_power'] for v in oldmodel['filters']]).T
    active=np.array(plan['active_detail_band_indices'])
    weight=1/np.maximum(target[active,0],1e-20)
    debt=target[active,0]-current[active,0]
    power,residual=nnls(matrix[np.ix_(active,active)]*weight[:,None],np.maximum(debt,0)*weight)
    full=np.zeros(8);full[active]=power
    assert np.array_equal(full[:4],np.zeros(4))
    profile=dict(schema='vsl.resonant-detail-offline/2',sample_rate=rate,acoustic_root_hz=46.875,
        plan=plan,original_DNA=dict(file=source.relative_to(repo).as_posix(),sha256=sha(source)),
        independent_LF=dict(file=accepted['model'],sha256=accepted['model_sha256'],scale=accepted['low_scale']),
        inherited_filter_profile_sha256=sha(repo/'voices/resonant_detail_v1/detail.json'),
        filters=oldmodel['filters'],stereo_R_over_L=oldmodel['stereo_R_over_L'],
        kernel_plan=oldmodel['plan'],detail_amplitude_gain=np.sqrt(full).tolist(),
        source_trajectory_stored=False,room_model=False,physical_modes_identified=False,human_accepted=False)
    output=a.out/'detail_model.json'
    output.write_text(json.dumps(profile,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    with (repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig') as f:index=list(csv.DictReader(f))
    assert len(index)==478
    for row in index:assert sha(repo/row['文件'])==row['SHA-256']
    r.update(result='fit_and_mask_controls_pass',plan=plan,model_sha256=sha(output),
        DNA_model_sha256=sha(model_path),DNA_stem_sha256=sha(a.out/'protected_dna.wav'),
        C_command=command,C_subtraction_error_FS=oracle_error,scalar_mask_error=mask_error,
        harmonic_rows_below_3k_exact=True,protected_detail_gains_zero=True,
        predicted_active_power_error_db=(10*np.log10((current[:,0]+matrix@full)[active]/target[active,0])).tolist(),
        negative_active_debt_bands=active[debt<0].tolist(),low_scale=accepted['low_scale'],
        C_H_unchanged=478,no_new_filter_fit=True)
    print(json.dumps({k:r[k] for k in ('result','C_subtraction_error_FS','predicted_active_power_error_db')}),flush=True)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:(a.out/'report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')

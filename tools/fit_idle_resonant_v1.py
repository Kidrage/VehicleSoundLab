"""Fit a separate stationary-low voice using the shared resonant-detail method."""
import argparse,csv,json,shutil,subprocess,sys
from pathlib import Path

p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--audit',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from scipy.optimize import nnls
from drive_evidence_v1.sources import sha
from sound_dna.profile import export
from residual_osc_v1.spectrum import matrices
from resonant_detail_v1.filters import fit,spectral_matrix_operator
from idle_texture_v1.profile import load,attenuate
from idle_texture_v1.envelope import fit as fit_envelope
from idle_texture_v1.power import theory,controls

a.out.mkdir(parents=True,exist_ok=False)
r=dict(schema='vsl.idle-resonant-fit/1',result='running',input_sha256={},source_sha256={},trials=[])
try:
    plan_path=repo/'research/idle_resonant_v1_plan.json';plan=json.loads(plan_path.read_text(encoding='utf-8'))
    audit=json.loads((a.audit/'report.json').read_text(encoding='utf-8'))
    assert audit['result']=='diagnostic_controls_pass'
    for name,digest in audit['source_sha256'].items():assert sha(repo/name)==digest,name
    for name,digest in audit['input_sha256'].items():assert sha(Path(name))==digest,name
    for path in [Path(__file__),plan_path,repo/'tools/sound_dna/profile.py',repo/'tools/sound_dna/statistics.py',
        repo/'tools/dna_texture_v2/observe.py',repo/'tools/drive_evidence_v1/sources.py',
        repo/'tools/residual_osc_v1/spectrum.py',*sorted((repo/'tools/idle_texture_v1').glob('*.py')),
        *sorted((repo/'tools/resonant_detail_v1').glob('*.py'))]:
        target=a.out/'exact_sources'/path.relative_to(repo);target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,target);r['source_sha256'][path.relative_to(repo).as_posix()]=sha(path)
    for path in [a.audit/'report.json',a.audit/'raw_reference.wav',a.audit/'normalized_reference.wav',a.audit/'C_DNA.wav']:
        r['input_sha256'][str(path)]=sha(path)
    source=repo/audit['plan']['base_model'];base,root=load(source)
    assert root==audit['acoustic_root_hz'];r['input_sha256'][str(source)]=sha(source)
    plan['cycle_frames']=48000/root
    raw,rate=sf.read(a.audit/'raw_reference.wav',always_2d=True);assert rate==48000
    normalized,rate=sf.read(a.audit/'normalized_reference.wav',always_2d=True);assert rate==48000
    r['controls']=controls(plan)
    envelopes=fit_envelope(normalized,root,plan)
    flat=[dict(coefficients=[0.]*24,enabled=False) for _ in plan['bands_hz']]
    # Existing AR fit only uses a flat integer-period budget here. The final
    # model is budgeted below with exact fractional-period sideband responses.
    models=fit(raw,dict(plan,cycle_frames=1024),flat)
    for model,envelope in zip(models,envelopes):
        model['envelope']=envelope
        model['theoretical_band_power']=spectral_matrix_operator(theory(model,root,plan),plan).tolist()
    matrix=np.array([v['theoretical_band_power'] for v in models]).T
    target=np.array([v['power'] for v in matrices(raw,plan['bands_hz'])]);ratio=np.sqrt(target[:,1]/target[:,0])
    exe=repo/'build-phase-texture-c-v1/bin/Release/VslSoundDna_probe.exe'
    r['input_sha256'][str(exe)]=sha(exe)
    original,rate=sf.read(a.audit/'C_DNA.wav',always_2d=True);assert rate==48000
    for amount in plan['replacement_amounts']:
        label='add_only' if not amount else 'replace35'
        candidate,gain=attenuate(base,root,amount,plan['harmonic_transition_hz'])
        file=a.out/(label+'.model');export(file,candidate,root)
        if not amount:assert file.read_bytes()==source.read_bytes()
        output=a.out/(label+'_DNA.wav')
        command=list(map(str,[exe,file,output,plan['seconds'],1,1,1]))
        done=subprocess.run(command,cwd=repo,capture_output=True,timeout=60)
        (a.out/(label+'_C.log')).write_bytes(done.stdout+done.stderr);assert done.returncode==0
        dna,rate=sf.read(output,always_2d=True);assert rate==48000
        if not amount:assert np.array_equal(dna[96000:],original)
        current=np.array([v['power'] for v in matrices(dna[plan['crop_start_frames']:],plan['bands_hz'])])
        debt=target[:,0]-current[:,0];assert min(debt)>=0,dict(label=label,debt=debt.tolist())
        weight=1/target[:,0];power,_=nnls(matrix*weight[:,None],debt*weight)
        prediction=current[:,0]+matrix@power
        r['trials'].append(dict(label=label,amount=amount,DNA_model_sha256=sha(file),DNA_stem_sha256=sha(output),
            detail_gain=np.sqrt(power).tolist(),C_command=command,
            predicted_power_error_db=(10*np.log10(prediction/target[:,0])).tolist(),
            low_rows_exact=True,zero_C_frozen_samples_exact=not amount))
    profile=dict(schema='vsl.idle-resonant-model/1',plan=plan,root_hz=root,filters=models,
        stereo_R_over_L=ratio.tolist(),trials=r['trials'],source_trajectory_stored=False,
        room_model=False,added_low_body=False,thermal_state_confirmed=False,RPM=None,
        origin=dict(segment=audit['plan']['source_segment'],seconds=audit['plan']['source_seconds']))
    model_path=a.out/'detail_model.json'
    model_path.write_text(json.dumps(profile,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    with (repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig') as f:index=list(csv.DictReader(f))
    assert len(index)==478
    for row in index:assert sha(repo/row['文件'])==row['SHA-256']
    r.update(result='fit_and_fractional_period_controls_pass',root_hz=root,model_sha256=sha(model_path),
        maximum_pole_radius=max(v['pole_radius'] for v in models),
        enabled_envelope_bands=[v['band_hz'] for v in models if v['envelope']['enabled']],
        C_H_unchanged=478,no_new_C_default_driver_or_listening_acceptance=True)
    print(json.dumps(dict(result=r['result'],root_hz=root,maximum_pole_radius=r['maximum_pole_radius'],
        envelope_bands=r['enabled_envelope_bands'],controls=r['controls'])),flush=True)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:(a.out/'report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')

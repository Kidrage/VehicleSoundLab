"""Fit startup-settling OSC detail to an immutable same-A stereo observation."""
import argparse,json,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from drive_evidence_v1.sources import sha,read
from residual_osc_v1.fit import export
from residual_osc_v1.spectrum import matrices
from stereo_field_v1.budget import matrix
from startup_detail_v1.budget import fit,BANDS,additive
from startup_detail_v1.controls import checks

a.out.mkdir(parents=True,exist_ok=False)
r=dict(result='running',human_accepted=False,source_sha256={},limits=[
    'Mixed same-A startup settling observation, not an isolated physical noise source',
    'No fast catch pitch, full startup timing or measured load/RPM calibration',
    'Fixed-Hz OSC detail and single acoustic anchor; not wide-RPM/detail modulation evidence',
    'Infeasible stereo bands remain silent; no automatic DNA attenuation or cross clipping',
    'Split of one short training passage is only local sensitivity, not independent recording validation'])
try:
    for source in [Path(__file__),*Path(__file__).with_name('startup_detail_v1').glob('*.py'),
                   repo/'tools/residual_osc_v1/spectrum.py',repo/'tools/residual_osc_v1/fit.py',
                   repo/'tools/stereo_field_v1/budget.py',repo/'tools/drive_evidence_v1/sources.py']:
        name=source.relative_to(repo).as_posix();dest=a.out/'exact_sources'/name
        dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,dest);r['source_sha256'][name]=sha(source)
    _,r['approved_input']=read(a.workspace,'A_start_context','audio_onset_observation')
    frozen=a.workspace/'baselines/startup_catch_v1'
    manifest=json.loads((frozen/'manifest.json').read_text(encoding='utf-8'))
    identities={v['path']:v['sha256'] for v in manifest['files']}
    def bound(name):
        file=frozen/name;assert sha(file)==identities[name],name
        r.setdefault('inputs',{})[name]=sha(file);return file
    reference,rate=sf.read(bound('evidence/render1/fixed_reference_float.wav'),always_2d=True)
    base,rate2=sf.read(bound('evidence/render1/renders/fixed_1.0.wav'),always_2d=True)
    assert rate==rate2==48000 and len(base)==384000
    r['controls']=checks()
    r['rows']=fit(reference,base[24000:])
    # Mean target fitted once. Reversing passage halves is reported separately.
    r['local_halves']=[]
    for side in (0,1):
        train=np.array_split(reference,2)[side];held=np.array_split(reference,2)[1-side]
        rows=fit(train,base[24000:])
        observations=matrices(held,BANDS)
        r['local_halves'].append(dict(training_half=side,rows=[dict(hz=v['hz'],accepted=v['accepted'],
            minimum_eigenvalue_relative=v['minimum_eigenvalue_relative'],
            held_target_power_change_dB=(10*np.log10(np.asarray(o['power'])/v['target']['power'])).tolist())
            for v,o in zip(rows,observations)]))
    export(a.out/'A startup settling detail.residual',r['rows'])
    sf.write(a.out/'reference_float.wav',reference,48000,subtype='FLOAT')
    profile=a.out/'A startup settling detail.residual'
    r['profile']=dict(file=profile.name,sha256=sha(profile),bands=len(BANDS),partials=32,
        active_bands=sum(v['accepted'] for v in r['rows']))
    r['DNA_sha256']=sha(repo/'voices/startup_settle_v1/A start cabin settle.model')
    with (repo/'handoff/C文件索引.csv').open('rb') as stream:r['source_index_sha256']=sha(repo/'handoff/C文件索引.csv')
    r.update(result='same_A_additive_stereo_candidate_fitted')
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:(a.out/'report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(result=r['result'],profile=r['profile'],infeasible=[v['hz'] for v in r['rows'] if not v['accepted']])))

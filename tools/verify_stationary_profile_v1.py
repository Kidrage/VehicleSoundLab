"""Exercise parameter fitting, serialization and existing C on known fixtures."""
import argparse
import json
from pathlib import Path
import shutil
import sys

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--validated',type=Path,required=True)
p.add_argument('--probe',type=Path,required=True)
p.add_argument('--out',type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from drive_evidence_v1.sources import sha
from exterior_clock_v1.warp import render_positions
from stationary_dna_v1.fixtures import make
from stationary_dna_v1.fit import fit,normalized_playback
from stationary_dna_v1.measure import moments,difference

a.out.mkdir(parents=True,exist_ok=False)
r=dict(schema='vsl.stationary-profile-C-controls/1',result='running',cases=[],sources={})
try:
    plan_path=repo/'research/B_stationary_dna_v1_validation_plan.json'
    plan=json.loads(plan_path.read_text(encoding='utf-8'))
    validation=json.loads((a.validated/'report.json').read_text(encoding='utf-8'))
    assert validation['result']=='passed' and validation['plan_sha256']==sha(plan_path)
    for name,digest in validation['sources'].items():assert sha(repo/name)==digest
    sources=[Path(__file__),plan_path]
    for package in ('stationary_dna_v1','sound_dna','exterior_clock_v1'):
        sources+=list((repo/'tools'/package).glob('*.py'))
    for source in sources:
        relative=source.relative_to(repo);target=a.out/'exact_sources'/relative
        target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
        r['sources'][relative.as_posix()]=sha(source)
    (a.out/'bin').mkdir();shutil.copy2(a.probe,a.out/'bin'/a.probe.name)
    r['probe_sha256']=sha(a.probe)
    r['validation_report_sha256']=sha(a.validated/'report.json')
    # Gates are stated before measuring C results. These controls only prove
    # that new parameter files can pass through the existing C source.
    r['rules']=dict(maximum_known_heldout_band_power_error_db=1,
                    maximum_known_heldout_complex_correlation_error=.05,
                    minimum_pitch_scaling_spectral_cosine=.995,
                    seconds_per_render=20)
    for case in plan['references']:
        root=case['root_hz'];reference=case['reference']
        audio,t,phase=make(root,reference,'steady',8)
        positions=np.arange(1,7,1/(1024*root))
        normalized=render_positions(audio,0,positions,min(14000,.38*1024*root))
        split=len(normalized)//2048*1024
        train,heldout=normalized[:split],normalized[split:]
        out=a.out/f'root{root:g}'
        item=dict(root_hz=root,reference=reference,fixture_kind='steady',
                  candidate=fit(train,root,plan,out,a.probe))
        sf.write(out/'known_source.wav',audio,48000,subtype='FLOAT')
        generated,_=sf.read(out/'detail.wav',always_2d=True)
        aligned=normalized_playback(generated[48000:],root)
        generated_moments=moments(aligned,root,plan['harmonics'],plan['bands_hz'])
        delta=difference(moments(heldout,root,plan['harmonics'],plan['bands_hz']),generated_moments)
        maximum=float(abs(np.array(delta['power_difference_db_LR'])).max())
        correlation=float(max(delta['complex_correlation_difference']))
        cosine=[]
        base=generated_moments[0]
        for name,pitch in [('lower',.9),('higher',1.1)]:
            pitched,_=sf.read(out/f'{name}.wav',always_2d=True)
            n=normalized_playback(pitched[48000:],root*pitch)
            observed=moments(n,root,plan['harmonics'],plan['bands_hz'])[0]
            values=np.sum(base*observed,axis=0)/np.sqrt(np.sum(base*base,axis=0)*np.sum(observed*observed,axis=0))
            cosine.extend(values.tolist())
        item.update(known_heldout_delta=delta,maximum_power_error_db=maximum,
                    maximum_complex_correlation_error=correlation,pitch_scaling_spectral_cosine=cosine,
                    passed=bool(maximum<=r['rules']['maximum_known_heldout_band_power_error_db'] and
                    correlation<=r['rules']['maximum_known_heldout_complex_correlation_error'] and
                    min(cosine)>=r['rules']['minimum_pitch_scaling_spectral_cosine']))
        r['cases'].append(item)
        print(json.dumps({k:item[k] for k in ('root_hz','maximum_power_error_db','maximum_complex_correlation_error','pitch_scaling_spectral_cosine','passed')}),flush=True)
    r.update(result='passed' if all(v['passed'] for v in r['cases']) else 'rejected',
             actual_vehicle_models_exported=False,runtime_modified=False,
             limits='Analytic synthetic controls, not real idle/acceleration, listening, device or generic phase qualification')
except Exception as exc:
    r.update(result='failed',error=repr(exc));raise
finally:
    (a.out/'report.json').write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8')

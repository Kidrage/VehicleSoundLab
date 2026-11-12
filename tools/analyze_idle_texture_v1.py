"""Locate low-speed source texture gaps before choosing a new idle source model."""
import argparse,csv,json,shutil,sys
from pathlib import Path

p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--out',type=Path,required=True);a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from drive_evidence_v1.sources import read,sha
from dna_texture_v2.observe import analytic_band,repeat
from residual_osc_v1.spectrum import matrices,error

a.out.mkdir(parents=True,exist_ok=False)
r=dict(schema='vsl.idle-texture-audit/1',result='running',input_sha256={},source_sha256={})
try:
    plan_path=repo/'research/idle_texture_v1_plan.json'
    plan=json.loads(plan_path.read_text(encoding='utf-8'));r['plan']=plan
    for path in [Path(__file__),plan_path,repo/'tools/drive_evidence_v1/sources.py',
                 repo/'tools/dna_texture_v2/observe.py',repo/'tools/residual_osc_v1/spectrum.py']:
        target=a.out/'exact_sources'/path.relative_to(repo);target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,target);r['source_sha256'][path.relative_to(repo).as_posix()]=sha(path)
    model=repo/plan['base_model'];tokens=model.read_text(encoding='ascii').splitlines()[0].split()
    root=float(tokens[7]);assert 5<root<20
    r['input_sha256'][str(model)]=sha(model)
    metric=dict(plan,acoustic_cycle_frames=round(48000/root))
    raw,provenance=read(a.workspace,plan['source_segment'],plan['source_use'])
    first,stop=[round((s-provenance['seconds'][0])*48000) for s in plan['source_seconds']]
    raw=raw[first:stop];r['provenance']=provenance
    freeze=a.workspace/'baselines/exterior_anchors_v1'
    manifest_path=freeze/'manifest.json';manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    mapping={v['path']:v['sha256'] for v in manifest['files']}
    r['input_sha256'][str(manifest_path)]=sha(manifest_path)
    def frozen(name):
        path=freeze/name;assert sha(path)==mapping[name]
        r['input_sha256'][str(path)]=sha(path)
        x,rate=sf.read(path,always_2d=True);assert rate==48000
        return x
    normalized=frozen('evidence/anchors_v2/A Stationary Low/fixed_reference_float.wav')
    generated=frozen('evidence/anchors_v2/A Stationary Low/raw_1.0.wav')[96000:]
    sf.write(a.out/'raw_reference.wav',raw,48000,subtype='FLOAT')
    sf.write(a.out/'normalized_reference.wav',normalized,48000,subtype='FLOAT')
    sf.write(a.out/'C_DNA.wav',generated,48000,subtype='FLOAT')
    target=matrices(raw,plan['bands_hz']);controls=[]
    # Fixed harmonics/noise at the new ~100ms coordinate, independent of any
    # measured engine signal. Keep all band/control failures in the report.
    rng=np.random.default_rng(561207);t=np.arange(len(raw))/48000
    for band in plan['bands_hz']:
        orders=np.unique(np.linspace(np.ceil(band[0]/root)+1,np.floor(band[1]/root)-1,15).astype(int))
        phase=rng.uniform(-np.pi,np.pi,len(orders))
        x=np.cos(2*np.pi*t[:,None]*root*orders+phase).sum(axis=1)/np.sqrt(len(orders))
        comb=np.column_stack((x,.7*x));noise=rng.normal(size=comb.shape)
        c,ce=repeat(analytic_band(comb,band,metric),metric)
        n,ne=repeat(analytic_band(noise,band,metric),metric)
        scaled,se=repeat(analytic_band(comb*7,band,metric),metric)
        minimum=min(v['maximum_repeat'] for v in c);maximum=max(v['maximum_repeat'] for v in n)
        invariant=max(abs(v['maximum_repeat']-u['maximum_repeat']) for v,u in zip(c,scaled))
        row=dict(band_hz=band,minimum_comb_repeat=minimum,maximum_noise_repeat=maximum,
            direct_error=max(ce,ne,se),gain_invariance_error=invariant)
        controls.append(row)
    r['controls']=controls
    assert all(v['minimum_comb_repeat']>=plan['controls']['comb_minimum_repeat']
        and v['maximum_noise_repeat']<=plan['controls']['noise_maximum_repeat']
        and v['direct_error']<plan['controls']['direct_error'] and v['gain_invariance_error']<1e-12 for v in controls),controls
    observations=[]
    for name,x in [('raw',raw),('normalized',normalized),('C_DNA',generated)]:
        power=matrices(x,plan['bands_hz']);bands=[]
        # Equal first block duration for repeat; mean Welch power uses full
        # available clips and is explicitly descriptive, not a matched path.
        block=x[:min(len(raw),len(normalized))]
        for i,band in enumerate(plan['bands_hz']):
            values,err=repeat(analytic_band(block,band,metric),metric)
            supported=all(np.array(power[i]['power'])>=np.array(target[i]['power'])*plan['unsupported_relative_band_power'])
            bands.append(dict(band_hz=band,power=power[i]['power'],repeat=values,
                supported_relative_to_raw=bool(supported),direct_error=err))
        observations.append(dict(name=name,frames=len(x),repeat_block_frames=len(block),bands=bands,
            spectral_errors=error(target,power)))
    r['observations']=observations
    r['raw_half_power']= [matrices(x,plan['bands_hz']) for x in np.array_split(raw,2)]
    with (repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig') as f:index=list(csv.DictReader(f))
    assert len(index)==478
    for row in index:assert sha(repo/row['文件'])==row['SHA-256']
    r.update(result='diagnostic_controls_pass',acoustic_root_hz=root,nominal_cycle_frames=metric['acoustic_cycle_frames'],
        C_H_unchanged=478,new_model=False,source_thermal_state=None,source_RPM=None,
        limits=['Band-lag correlation is not a physical noise fraction or a quality rating',
            'Raw, normalized and C clips differ in clock/support; no unique filter-loss attribution',
            'Normalized analysis is source-antialiased; no interpretation of absent HF repeat',
            'No 35percent moving-context recipe transfer to idle; accepted moving timbre remains unchanged'])
    print(json.dumps(dict(result=r['result'],observations=[dict(name=v['name'],
        bands=[dict(hz=b['band_hz'],repeat=b['repeat'][0]['maximum_repeat'],supported=b['supported_relative_to_raw'],
            power_error_db=v['spectral_errors'][i]['power_delta_db'][0]) for i,b in enumerate(v['bands'])]) for v in observations])),flush=True)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:(a.out/'report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')

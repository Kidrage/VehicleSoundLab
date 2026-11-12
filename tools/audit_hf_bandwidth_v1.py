"""Audit raw/normalized/C bandwidth and export isolated raw-Hz OSC candidates."""
import argparse
import csv
import json
from pathlib import Path
import shutil
import sys

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--out',type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from drive_evidence_v1.sources import read,sha
from hf_bandwidth_v1.observe import observe,budget,known_controls,BANDS
from residual_osc_v1.fit import export

a.out.mkdir(parents=True,exist_ok=False)
r=dict(schema='vsl.hf-bandwidth-audit/1',result='running',human_accepted=False,
       runtime_changed=False,input_sha256={},source_sha256={},contexts=[],limits=[
           'Raw stereo is a mixed microphone observation, not separated exhaust or mechanical HF',
           'Normalized reference has a different clock/support; mean differences do not isolate filter loss',
           'C is a fixed acoustic anchor: no measured RPM, load or fast startup calibration',
           'Additive fixed-Hz profiles model mean stereo covariance, not original transient detail',
           'No default model replacement, DNA attenuation or automatic cross-covariance clipping'])
try:
    paths=[Path(__file__),repo/'tools/hf_bandwidth_v1/observe.py',
           repo/'tools/drive_evidence_v1/sources.py',repo/'tools/residual_osc_v1/spectrum.py',
           repo/'tools/residual_osc_v1/fit.py',repo/'tools/startup_detail_v1/budget.py',
           repo/'tools/stereo_field_v1/budget.py']
    for path in paths:
        name=path.relative_to(repo).as_posix();dest=a.out/'exact_sources'/name
        dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,dest)
        r['source_sha256'][name]=sha(path)
    def bound(folder,name):
        root=a.workspace/'baselines'/folder;manifest=root/'manifest.json'
        expected=next(v['sha256'] for v in json.loads(manifest.read_text(encoding='utf-8'))['files'] if v['path']==name)
        path=root/name;assert sha(path)==expected,str(path)
        r['input_sha256'][str(path)]=expected;r['input_sha256'][str(manifest)]=sha(manifest)
        audio,rate=sf.read(path,always_2d=True);assert rate==48000
        return audio
    cases=[dict(name='A cabin startup settling',key='startup',segment='A_start_context',
                use='audio_onset_observation',seconds=(38.48,39.51),
                folder='startup_catch_v1',reference='evidence/render1/fixed_reference_float.wav',
                base='evidence/render1/renders/fixed_1.0.wav',
                model='voices/startup_settle_v1/A start cabin settle.model',
                bands=[(8000,10000),(10000,12000),(12000,14000),(14000,16000)]),
           dict(name='A stationary rear low',key='stationary_low',segment='A_exterior_blips',
                use='exterior_dynamic_observation',seconds=(243.9,247.1),
                folder='exterior_anchors_v1',
                reference='evidence/anchors_v2/A Stationary Low/fixed_reference_float.wav',
                base='evidence/anchors_v2/A Stationary Low/raw_1.0.wav',
                model='voices/exterior_anchors_v1/A Stationary Low.model',
                bands=[(3000,3800),(3800,4800),(4800,6000),(6000,8000),
                       (8000,10000),(10000,12000),(12000,14000),(14000,16000)])]
    r['known_controls']=known_controls()
    for case in cases:
        raw,provenance=read(a.workspace,case['segment'],case['use'])
        origin=provenance['seconds'][0]
        begin,end=[round((s-origin)*48000) for s in case['seconds']]
        raw=raw[begin:end];assert len(raw)==round((case['seconds'][1]-case['seconds'][0])*48000)
        normalized=bound(case['folder'],case['reference'])
        base=bound(case['folder'],case['base'])[96000:]
        assert len(base)>=4*48000 and np.isfinite(base).all()
        tokens=(repo/case['model']).read_text().splitlines()[0].split()
        r['input_sha256'][str(repo/case['model'])]=sha(repo/case['model'])
        rows=budget(raw,base,case['bands'])
        out=a.out/case['key'];out.mkdir()
        export(out/'raw_Hz_candidate.residual',rows)
        sf.write(out/'raw_reference_float.wav',raw,48000,subtype='FLOAT')
        sf.write(out/'C_base_float.wav',base,48000,subtype='FLOAT')
        halves=[observe(part) for part in np.array_split(raw,2)]
        r['contexts'].append(dict(name=case['name'],key=case['key'],seconds=case['seconds'],
            provenance=provenance,model=case['model'],harmonics=int(tokens[5]),base_hz=float(tokens[7]),
            highest_retained_line_hz=int(tokens[5])*float(tokens[7]),
            raw=observe(raw),normalized=observe(normalized),C=observe(base),raw_halves=halves,
            budget=rows,candidate_sha256=sha(out/'raw_Hz_candidate.residual')))
    with (repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig') as stream:index=list(csv.DictReader(stream))
    for row in index:assert sha(repo/row['文件'])==row['SHA-256'],row['文件']
    r.update(result='raw_Hz_observed_candidates_exported',indexed_C_H_unchanged=len(index))
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:(a.out/'report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(result=r['result'],contexts=[dict(key=c['key'],
    active_bands=[v['hz'] for v in c['budget'] if v['accepted']],
    rejected_bands=[v['hz'] for v in c['budget'] if not v['accepted']]) for c in r['contexts']])))

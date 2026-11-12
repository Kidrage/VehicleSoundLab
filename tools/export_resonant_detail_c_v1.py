"""Encode existing immutable detail parameters; no fitting or timbre changes."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--out',type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sha=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest()
a.out.mkdir(parents=True,exist_ok=False)
voices=repo/'voices/resonant_detail_c_v1';voices.mkdir(exist_ok=False)
result=dict(schema='vsl.resonant-detail-c-export/1',profiles=[],source_sha256=sha(__file__))
for label,source,preset in [('moving_35','resonant_detail_v1','replace_35'),
                           ('idle_add','idle_resonant_v1','add_only'),
                           ('idle_35','idle_resonant_v1','replace35')]:
    original=repo/'voices'/source/'detail.json'
    data=json.loads(original.read_text(encoding='utf-8'))
    choice=next(v for v in data['presets'] if v['name']==preset)
    gains=choice.get('detail_amplitude_gain',choice.get('detail_gain'))
    ratios=data['kernel'].get('stereo_R_over_L',data.get('stereo_R_over_L'))
    count=len(data['filters']);assert count==len(gains)==len(ratios)
    lines=[f"VSL_RESONANT_DETAIL 1 48000 {count} {data['kernel']['warmup_frames']} {data['acoustic_root_hz']:.17g}"]
    for model,gain,ratio in zip(data['filters'],gains,ratios):
        beta=model['envelope']['coefficients']
        assert len(beta)%2==0 and len(beta)<=24
        if not any(beta):beta=[]
        lines.append(f"{len(model['a'])-1} {len(model['sos'])} {len(beta)//2}")
        lines.append(' '.join(f'{v:.17g}' for v in [*model['band_hz'],model['sigma'],gain,ratio]))
        lines.append(' '.join(f'{v:.17g}' for v in model['a']))
        lines.extend(' '.join(f'{v:.17g}' for v in row) for row in model['sos'])
        if beta:lines.append(' '.join(f'{v:.17g}' for v in beta))
    text='\n'.join(lines)+'\n';path=voices/f'{label}.rdetail'
    path.write_text(text,encoding='ascii',newline='\n');shutil.copy2(path,a.out/path.name)
    result['profiles'].append(dict(name=label,file=path.relative_to(repo).as_posix(),sha256=sha(path),
        original=original.relative_to(repo).as_posix(),original_sha256=sha(original),preset=preset,
        recipe=choice,bands=count,root_hz=data['acoustic_root_hz'],
        source_human_scope='held offline moving35' if label=='moving_35' else 'idle candidate pending listening',
        native_listening_accepted=False,driver_integrated=False))
    shutil.copy2(original,a.out/f'{label}_source.json')
result.update(result='encoded_existing_parameters',kernel_only=True,new_fitting=False)
for target in (a.out/'report.json',voices/'index.json'):
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
shutil.copy2(__file__,a.out/'executed_export.py')
print(json.dumps(dict(result=result['result'],profiles=[v['file'] for v in result['profiles']])))

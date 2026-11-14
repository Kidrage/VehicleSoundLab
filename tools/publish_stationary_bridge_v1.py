"""Publish only the aperture that passed the frozen qualification and C gates."""
import argparse,shutil
from pathlib import Path
from research_archive_v1 import load,save,sha
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--fit',type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];r=load(a.fit/'report.json')
assert r['result']=='qualified_bridge_voices_rendered'
assert [v['name'] for v in r['anchors']]==['A Bridge Mid Two'] and len(r['rejected'])==2
out=repo/'voices/stationary_bridge_v1';out.mkdir(exist_ok=False)
row=r['anchors'][0];name=row['name'];folder=a.fit/name
for suffix,key in [('model','DNA_sha256'),('rdetail','detail_sha256')]:
    source=folder/('voice.model' if suffix=='model' else 'detail.rdetail')
    assert sha(source)==row[key];shutil.copy2(source,out/(name+'.'+suffix))
save(out/'index.json',dict(schema='vsl.stationary-bridge-profiles/1',status='candidate; hearing pending',
    name=name,root_hz=row['root_hz'],DNA_sha256=row['DNA_sha256'],detail_sha256=row['detail_sha256'],
    source=r['source'],source_seconds=row['phase']['source_seconds'],heldout_coherence=row['heldout_coherence'],
    maximum_LR_band_error_db=max(v['maximum_LR_band_error_db'] for v in row['renders']),
    rejected=[dict(name=v['name'],root_hz=v['root_hz'],heldout_coherence=v['heldout_coherence']) for v in r['rejected']],
    support_gaps_hz=r['remaining_support_gaps_hz'],human_accepted=False,
    limits='One falling-rev observation, not measured RPM/load or a new real engine. Original common-clock qualification remains limited. No new room, recorded timeline or native default.'))
print('One qualified source observation published; two rejected apertures remain excluded.')

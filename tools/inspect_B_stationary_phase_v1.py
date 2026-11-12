"""Measure all existing low-order probes on a fixed, already fitted coordinate.

No new reference/window/interval fit; the earlier local gate stays rejected.
"""
import argparse,json,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True);p.add_argument('--qualified',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import soundfile as sf
from startup_catch_v1.clock import diagnostics
from phase_clock_v1.projection import independent_agreement
from drive_evidence_v1.sources import sha
a.out.mkdir(parents=True,exist_ok=False)
for file in [Path(__file__),repo/'tools/startup_catch_v1/clock.py',repo/'tools/phase_clock_v1/projection.py']:
    target=a.out/file.name;shutil.copy2(file,target)
r=dict(schema='vsl.B-stationary-all-low-probes/1',input_report_sha256=sha(a.qualified/'report.json'),cases={},model_exported=False)
previous=json.loads((a.qualified/'report.json').read_text(encoding='utf-8'))
for name,item in previous['cases'].items():
    assert not item['local_diagnostic_gate']
    reference=item['case']['primary_reference'];source=a.qualified/name/f'reference{reference}_normalized.wav'
    audio,rate=sf.read(source,always_2d=True);assert rate==48000
    values=diagnostics(audio,reference);agreement=independent_agreement(values)
    r['cases'][name]=dict(normalized_sha256=sha(source),all_low_order_diagnostics=values,
        agreement=agreement,original_local_gate=False,reference=reference)
    print(json.dumps(dict(case=name,agreement=agreement,probes={k:v for k,v in values.items() if v['supported_fraction']>=.8})),flush=True)
(a.out/'report.json').write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8')

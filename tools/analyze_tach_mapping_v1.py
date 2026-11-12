"""Recheck E's existing tach intervals without inventing exact RPM telemetry."""
import argparse
import json
from pathlib import Path
import shutil
import sys

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
from drive_evidence_v1.sources import sha,read
from tach_mapping_v1.intervals import evaluate,known_controls

a.out.mkdir(parents=True,exist_ok=False)
r=dict(schema='vsl.tach-mapping/1',result='running',source_sha256={},input_sha256={},sensitivities=[],
       runtime_changed=False,human_timbre_accepted=False,limits=[
           'E high-rev cabin only; these visual intervals are not ECU telemetry or precise RPM targets',
           'Shared time offset includes unknown A/V, display and observation latency; its causes are not separated',
           'Offset grid +/-0.6s and acoustic perturbations0/1/2percent are design sensitivity, not confidence bounds',
           'Existing acoustic family is reused; this does not requalify instantaneous phase tracking or source separation',
           'Missing acoustic support is untested, never extrapolated or counted as an incompatible reading',
           'Not transferred to A startup/exterior, B or D, and not a new driving control trajectory'])
try:
    paths=[Path(__file__),repo/'tools/tach_mapping_v1/intervals.py',repo/'tools/drive_evidence_v1/sources.py']
    for path in paths:
        name=path.relative_to(repo).as_posix();dest=a.out/'exact_sources'/name
        dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,dest);r['source_sha256'][name]=sha(path)
    _,r['approved_input']=read(a.workspace,'E_corsa_second_context','cabin_dynamic_observation')
    root=a.workspace/'baselines/drive_evidence_v1';manifest=json.loads((root/'manifest.json').read_text(encoding='utf-8'))
    def bound(name):
        expected=next(v['sha256'] for v in manifest['files'] if v['path']==name)
        file=root/name;assert sha(file)==expected,name;r['input_sha256'][str(file)]=expected;return file
    report=json.loads(bound('evidence/summary_v3/report.json').read_text(encoding='utf-8'))
    annotation_path=repo/'research/drive_evidence_v1_annotations.json'
    assert sha(annotation_path)==report['annotation_sha256']
    annotation=json.loads(annotation_path.read_text(encoding='utf-8'))
    r['input_sha256'][str(annotation_path)]=sha(annotation_path)
    r['input_sha256'][str(root/'manifest.json')]=sha(root/'manifest.json')
    family=report['family'];assert family['status']=='connected_observed_family'
    times=np.array([v['seconds'] for v in family['rows']]);hz=np.array([v['root_hz'] for v in family['rows']])
    offsets=np.arange(-60,61)*.01;r['known_controls']=known_controls()
    for error in (0,.01,.02):
        rows=evaluate(times,hz,annotation['tach_intervals'],offsets,error)
        compatible=[v for v in rows if v['feasible']]
        supports_default=[v['display_minus_audio_seconds'] for v in compatible
                          if v['root_per_rpm_interval'][0]<=1/120<=v['root_per_rpm_interval'][1]]
        r['sensitivities'].append(dict(acoustic_fraction=error,rows=rows,feasible_offsets=len(compatible),
            unsupported_offsets=sum(not v['all_readings_supported'] for v in rows),
            union_envelope_root_per_rpm=[min(v['root_per_rpm_interval'][0] for v in compatible),
                                        max(v['root_per_rpm_interval'][1] for v in compatible)] if compatible else None,
            default_1_over_120_supported_offsets=supports_default))
    voices=json.loads((repo/'voices/cabin_anchors_v1/index.json').read_text(encoding='utf-8'))
    r['anchor_interpretation']=dict(default_root_per_rpm=1/120,
        warning='The following nominal RPM is conditional on the1/120mapping; an acoustic anchor is not a measured RPM point',
        voices=voices)
    r.update(result='E_mapping_interval_sensitivity_observed')
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:(a.out/'report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(result=r['result'],summary=[{k:v for k,v in row.items() if k!='rows'} for row in r['sensitivities']])))

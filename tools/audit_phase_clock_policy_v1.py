"""Audit whole-path fallback on independently saved identical A contexts."""
import argparse,json,sys
from pathlib import Path
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',required=True,type=Path)
parser.add_argument('--out',required=True,type=Path)
args=parser.parse_args();sys.path.insert(0,str(args.workspace/'tools/python_deps'))
from drive_evidence_v1.sources import sha
root=args.workspace/'references/analysis'
old_path=root/'state_colour_v2/clocks_attempt2/report.json';new_path=root/'phase_clock_v1/chirplet_real/report.json'
old=json.loads(old_path.read_text(encoding='utf-8'));new=json.loads(new_path.read_text(encoding='utf-8'))
assert old['source']==new['source'] and old.keys()>= {'cases'} and old['cases'].keys()==new['cases'].keys()
report=dict(schema='vsl.phase-clock-policy-audit/1',source=old['source'],cases={},selection={},
    input_sha256=dict(fft=sha(old_path),chirplet=sha(new_path)),
    rule='Use an unchanged complete FFT path; only a whole FFT failure permits whole chirplet fallback; never combine incomplete rows')
for name,paths in old['cases'].items():
    report['cases'][name]={};report['selection'][name]={}
    for ref,path in paths.items():
        choice=path if path['rows'] else new['cases'][name][ref]
        selected='fft' if path['rows'] else 'chirplet' if choice['rows'] else None
        assert not path['rows'] or choice==path
        report['cases'][name][ref]=choice;report['selection'][name][ref]=selected
report['connected_reference5']=sum(bool(x['5']['rows']) for x in report['cases'].values())
report['connected_reference10']=sum(bool(x['10']['rows']) for x in report['cases'].values())
assert report['connected_reference5']==7 and report['connected_reference10']==0
assert not report['cases']['rise3']['5']['rows']
repo=Path(__file__).resolve().parents[1]
report['source_sha256']={p.relative_to(repo).as_posix():sha(p) for p in (Path(__file__),repo/'tools/phase_clock_v1/tracking.py')}
args.out.mkdir(parents=True,exist_ok=False)
(args.out/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(connected5=report['connected_reference5'],connected10=report['connected_reference10'],rise3='still excluded',all_prior_paths_unchanged=True)))

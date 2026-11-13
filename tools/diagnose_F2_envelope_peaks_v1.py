"""Trace the preserved fixture's native candidates; never read recording or fit."""
import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import sys

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
args=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
from drive_evidence_v1.sources import sha

args.out.mkdir(parents=True,exist_ok=False)
report=dict(schema='vsl.F2-envelope-peaks-diagnosis/1',result='running',sources={},real_audio_read=False,
    model_exported=False,runtime_changed=False,calls=[],completed_fixture_ids=[])
try:
    failed=args.workspace/'references/analysis/F2_local_envelopes_v1/observe1'
    package=failed/'exact_sources/tools/line_motion_v1'
    spec=importlib.util.spec_from_file_location('failed_envelope_fixture',package/'__init__.py',submodule_search_locations=[str(package)])
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
    from importlib import import_module
    controls=import_module(spec.name+'.envelope_controls');original=controls.native_peaks
    def trace(*args,**kwargs):
        value=original(*args,**kwargs)
        report['calls'].append(dict(labels=args[2],selected=value['selected_native_bin_Hz'].tolist(),
            candidates=value['candidates']))
        return value
    controls.native_peaks=trace
    try:
        for fixture in controls.fixtures():report['completed_fixture_ids'].append(fixture['id'])
    except AssertionError as exc:
        assert str(exc)=='Fixed six-tone fixture must have exactly two low-region observed peaks'
        report['failure_replayed']=repr(exc)
    else:raise AssertionError('Expected fixture failure did not reproduce')
    for path in (Path(__file__),repo/'tools/drive_evidence_v1/sources.py'):
        relative=path.relative_to(repo);target=args.out/'exact_sources'/relative;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,target);report['sources'][relative.as_posix()]=sha(path)
    report.update(result='original_fixture_peak_count_failure_replayed_without_fit',failed_report_sha256=sha(failed/'report.json'))
    print(json.dumps(dict(result=report['result'],completed=report['completed_fixture_ids'],
        candidate_bins=[[p['native_bin_Hz'] for p in c['candidates'][4][0]] if len(c['candidates'])==5 else [] for c in report['calls']])),flush=True)
except Exception as exc:report.update(result='failed',error=repr(exc));raise
finally:(args.out/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')

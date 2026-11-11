"""Bind LF partition source, device/UI checks and every local artifact."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True)
parser.add_argument('--out',type=Path,required=True)
args=parser.parse_args()
repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
from drive_evidence_v1.sources import sha
assert not args.out.exists()
root=args.workspace/'references/analysis/harmonic_body_v1'
def read(name):return json.loads((root/name).read_text(encoding='utf-8'))
controls=read('controls/verification.json');budget=read('budget/report.json')
ui=read('ui/verification.json');page=read('review/browser_qa.json');review=read('review/report.json')
assert controls['result']==ui['result']==page['result']=='pass'
for report in (controls,budget,review):
    for name,expected in report['source_sha256'].items():assert sha(repo/name)==expected,name
assert sha(repo/'tools/verify_atlas_ui_v1.py')==ui['verifier_sha256']
assert sha(repo/'handoff-build/bin/Release/VslAtlasMonitor.exe')==ui['binary_sha256']
ctest=(root/'build/ctest_34.log').read_bytes()
assert ctest.count(b'Test Passed.')==34 and b'Test Failed.' not in ctest
devices={name:read('device/'+name+'.json') for name in ('bench','pedals','stopped','cabin_restart')}
assert all(r['healthy'] and r['offline_float_equal'] and r['queue_empty']==0 and r['budget_exceeded']==0 for r in devices.values())
accepted=json.loads((repo/'research/coherent_low_v1_acceptance.json').read_text(encoding='utf-8'))
assert sha(repo/accepted['model'])==accepted['model_sha256']
assert sha(repo/'voices/dna_bank_v1/V10 Exterior.model')==accepted['dna_model_sha256']
source_files=[Path(__file__),repo/'tools/freeze_harmonic_body_v1.py',repo/'tools/verify_atlas_ui_v1.py',
    repo/'tools/harmonic_body_v1/check_page.cjs',repo/'handoff/CMakeLists.txt',repo/'modules/dna_atlas/CMakeLists.txt',
    *sorted((repo/'experiments/atlas_monitor_v1').glob('*.[ch]')),
    *sorted((repo/'modules/harmonic_body').glob('*'))]
source_hashes={**controls['source_sha256'],**budget['source_sha256'],**review['source_sha256'],
    **{p.relative_to(repo).as_posix():sha(p) for p in source_files if p.is_file()}}
report=dict(schema='vsl.harmonic-body-published/1',date='2026-11-12',result='pass',tests=34,
    base_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
    human_accepted=False,accepted_moving_context_pair_unchanged=True,evidence_root=str(root),
    budget=budget['cases'],controls={k:v for k,v in controls.items() if k not in ('source_sha256','runs')},
    offline_runs=controls['runs'],devices=devices,ui=ui,browser=page,
    source_sha256=source_hashes,c_index_sha256=sha(repo/'handoff/C文件索引.csv'),
    binaries_sha256={n:sha(repo/'handoff-build/bin/Release'/n) for n in
        ('VslAtlasDrive_probe.exe','VslAtlasMonitor.exe','VslAtlasMonitor_device_verify.exe')},
    evidence_sha256={p.relative_to(root).as_posix():sha(p) for p in sorted(root.rglob('*'))
                     if p.is_file() and '__pycache__' not in p.parts},
    limits=controls['limits']+['Short muted device/UI checks, no new timbre or actual7.1.4 acceptance',
        'Old driving DSP/take protocol unchanged; new monitor control trace remains debug-only'])
args.out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(result='pass',tests=34,evidence_files=len(report['evidence_sha256']),
    max_device_ms=max(d['render_max_ms'] for d in devices.values())),ensure_ascii=False))

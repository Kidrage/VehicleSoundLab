"""Bind diagnostic evidence, explicit failed controls and unchanged driving output."""
import argparse
import csv
import json
from pathlib import Path
import sys
import urllib.parse
import urllib.request

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True)
args=parser.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
from drive_evidence_v1.sources import sha
root=args.workspace/'references/analysis/state_colour_v2'
def read(rel):return json.loads((root/rel).read_text(encoding='utf-8'))
fit=read('fit_attempt3/report.json');controls=read('controls_attempt2/report.json')
review=read('review/report.json');regression=read('regression/verification.json')
assert controls['result']=='fail' and controls['maximum_tracked_zero_shape_error_db']>.5
assert controls['maximum_zero_shape_error_db']<.001 and controls['maximum_known_shape_error_db']<.001
assert regression['result']=='pass' and len(regression['stems'])==19 and regression['trace_equal']
assert all(r['rms_error_db']<r['flat_rms_error_db'] for r in fit['folds'])
first=(root/'ctest_attempt1.log').read_bytes();focused=(root/'ctest_focused.log').read_bytes()
assert first.count(b'Test Passed.')==35 and first.count(b'Test Failed.')==1
assert focused.count(b'Test Passed.')==1 and b'Test Failed.' not in focused
with (repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig',newline='') as f:
    rows=list(csv.DictReader(f))
for row in rows:assert sha(repo/row['文件'])==row['SHA-256'],row['文件']

url='http://127.0.0.1:8789/research/'+urllib.parse.quote('工况声线诊断V2.html')
with urllib.request.urlopen(url,timeout=10) as response:
    assert response.status==200;page=response.read().decode('utf-8')
assert page.count('<audio controls')==6 and 'autoplay' not in page
http=[]
for name in ('base','half','rise','transition','reference1','reference4'):
    audio_url=f'http://127.0.0.1:8789/references/analysis/state_colour_v2/review/{name}.wav'
    with urllib.request.urlopen(audio_url,timeout=10) as response:
        assert response.status==200 and response.read(4)==b'RIFF'
        http.append(dict(name=name,status=200))

iterations=dict(clock=['attempt1: rise3 missing','attempt2: rise3 start shifted but still missing; excluded'],
    colour=['attempt1: original features','attempt2: same measurements, shared pure feature module'],
    fit=['attempt1: unrestricted endpoint extrapolation; retained','attempt2: unity from order128; retained',
         'attempt3: held-out predictions include normalization from training passages only; final diagnostic'],
    controls=['attempt1: dense carrier path mostly missing; failed','attempt2: resolved-carrier paths connect but1.20dB high-band spurious colour; failed0.5dB target'],
    c_tests=['attempt1:35pass/1fail; unsigned negation in analytic test expectation','focused: corrected test formula;1pass; no DSP change'],
    review=['attempt1: audio rendered, metadata read failed due default Windows text encoding','final: explicit UTF8,4C renders and19driving stems/trace verified'],
    human_accepted=False,driver_mapping=False)
(root/'iterations.json').write_text(json.dumps(iterations,indent=2)+'\n',encoding='utf-8',newline='\n')
sources=[p for folder in ('modules/osc_colour','experiments/state_colour_v2','tools/state_colour_v2')
         for p in (repo/folder).iterdir() if p.is_file()]
sources += [repo/p for p in ('modules/dna_atlas/voice.c','modules/dna_atlas/voice.h','handoff/CMakeLists.txt',
    'references/segments_v1.json','tools/analyze_state_colour_v2.py','tools/explore_state_colour_v2.py',
    'tools/fit_state_colour_v2.py','tools/verify_state_colour_v2.py','tools/review_state_colour_v2.py',
    'tools/summarize_state_colour_v2.py')]
report=dict(schema='vsl.state-colour-summary/1',scope='Independent diagnostic acoustic colour axis, not driver-state calibration',
    engineering_checks='pass',automatic_sweep_control='fail',human_accepted=False,driver_mapping=False,
    c_tests=dict(existing_passed=35,new_contract_passed=1,total=36,first_test_expectation_failure_preserved=True),
    c_index_sha256=sha(repo/'handoff/C文件索引.csv'),fit=fit,controls=controls,review=review,
    regression=dict(identical_wav_stems=19,trace_equal=True),page=url,page_http=http,
    browser_interaction_verified=False,evidence_root=str(root),
    source_sha256={p.relative_to(repo).as_posix():sha(p) for p in sources},
    evidence_sha256={p.relative_to(root).as_posix():sha(p) for p in sorted(root.rglob('*')) if p.is_file()},
    binary_sha256={name:sha(repo/'handoff-build'/sub/name) for name,sub in
                   [('VslOscColour_probe.exe','bin/Release'),('VslOscColour_checks.exe','Release')]},
    unchanged_model_sha256={p.relative_to(repo).as_posix():sha(p) for folder in ('dna_bank_v1','coherent_low_v1','exterior_anchors_v1','cabin_anchors_v1') for p in (repo/'voices'/folder).glob('*.model')},
    limits=['Three short repeats, acoustic-root45..50Hz only; overlapping windows are not replications',
            'Automatic tracking bias, mixed recording and unknown transfer; no physical source separation',
            'No new driver/UI/device/spatial/timbre acceptance; strict renderer identity changes on rebuild'])
(repo/'research/state_colour_v2_summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(engineering='pass',swept_control='fail',tests=36,identical_stems=19,http_audio=len(http),files=len(report['evidence_sha256']))))

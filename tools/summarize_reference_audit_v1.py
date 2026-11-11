"""Check preserved route evidence and independently recompute stereo metrics."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import traceback

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace', type=Path, required=True)
parser.add_argument('--verification', type=Path, required=True)
args = parser.parse_args()
repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(args.workspace/'tools/python_deps'))
import numpy as np


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


roots = {name:args.workspace/'references/analysis'/name for name in
         ('upstream_route_v1','stereo_delay_v1')}
args.verification.mkdir(parents=True, exist_ok=False)
shutil.copy2(__file__,args.verification/'executed_summary.py')


def failure(kind, value, trace):
    (args.verification/'report.json').write_text(json.dumps(dict(result='failed',
        source_sha256=sha(__file__),error=repr(value),
        traceback=''.join(traceback.format_exception(kind,value,trace))),indent=2)+'\n',encoding='utf-8')
    sys.__excepthook__(kind,value,trace)


sys.excepthook = failure
upstream = roots['upstream_route_v1']
fetch = read(upstream/'fetch2/report.json')
route = read(upstream/'analysis1/report.json')
startup = read(upstream/'startup1/report.json')
stereo = read(roots['stereo_delay_v1']/'analysis1/report.json')
assert all(r['result'] == 'pass' for r in (fetch, route, startup, stereo))
assert read(upstream/'fetch1/report.json')['result'] == 'failed'
for row in fetch['files']:
    path = upstream/'fetch2/text'/row['path']
    data = path.read_bytes()
    assert len(data) == row['bytes'] and sha(path) == row['sha256']
    assert hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest() == row['git_blob_sha1']
assert startup['fetch_report_sha256'] == route['fetch_report_sha256'] == sha(upstream/'fetch2/report.json')
assert startup['route_report_sha256'] == sha(upstream/'analysis1/report.json')
assert sha(upstream/'startup1/executed_inspector.py') == startup['source_sha256']
assert sha(upstream/'fetch2/executed_fetch.py') == fetch['fetcher_sha256']
for root, report in ((upstream/'analysis1',route),(roots['stereo_delay_v1']/'analysis1',stereo)):
    for name, digest in report['source_sha256'].items():
        assert sha(root/'exact_sources'/name) == digest, (root,name)

plan = read(repo/'research/stereo_delay_v1_plan.json')
assert sha(repo/'research/stereo_delay_v1_plan.json') == stereo['plan_sha256']
assert sha(args.workspace/'references/segments_v1.json') == stereo['catalog_sha256']
assert len(stereo['controls']) == 12
for control in stereo['controls']:
    for band in control['bands']:
        if control['coherence'] >= .9:
            assert abs(band['delay_seconds']-control['delay_seconds']) <= plan['known_delay_error_seconds']
        if control['delay_seconds']:
            assert band['test_rmse_reduction_fraction'] >= plan['known_delay_minimum_rmse_reduction_fraction']
        if not control['coherence']:
            assert not band['train_phase_qualified']

# Scalar frequency-bin sums independently check coefficients and weighted RMSE.
# Saved observations are the same data, so this is arithmetic validation only.
metric_errors, observations = [], []
for case in stereo['observations']:
    data = np.load(roots['stereo_delay_v1']/'analysis1'/(case['case']['name']+'_observations.npz'))
    assert len(data['left']) == case['blocks']
    assert case['scalar_dft_max_relative_error'] < 1e-10
    assert case['windows_per_block'] == int(data['windows_per_block'])
    for band_id, band in enumerate(case['bands']):
        lo, hi = band['hz']
        bins = [i for i,hz in enumerate(data['hz']) if lo <= hz < hi]
        frequencies = [data['hz'][i]-(lo+hi)/2 for i in bins]
        train, test = band['train_blocks'], band['test_blocks']
        assert set(train).isdisjoint(test) and sorted(train+test) == list(range(case['blocks']))
        cross = [sum(data['cross'][t,i] for t in train)/len(train) for i in bins]
        w = [(sum(data['left'][t,i] for t in train)*sum(data['right'][t,i] for t in train))**.5/len(train) for i in bins]
        observed = [z/max(v,1e-30) for z,v in zip(cross,w)]
        weights = [v/max(sum(w),1e-30) for v in w]
        scalar = sum(v*z for v,z in zip(weights,observed))
        a = sum(v*z*np.exp(2j*np.pi*f*band['delay_seconds']) for v,z,f in zip(weights,observed,frequencies))
        prediction = [a*np.exp(-2j*np.pi*f*band['delay_seconds']) for f in frequencies]
        old, new = [], []
        for block in test:
            w = [(data['left'][block,i]*data['right'][block,i])**.5 for i in bins]
            actual = [data['cross'][block,i]/max(v,1e-30) for i,v in zip(bins,w)]
            weights = [v/max(sum(w),1e-30) for v in w]
            old.append(sum(v*abs(z-scalar)**2 for v,z in zip(weights,actual)))
            new.append(sum(v*abs(z-p)**2 for v,z,p in zip(weights,actual,prediction)))
        old, new = (sum(old)/len(old))**.5, (sum(new)/len(new))**.5
        reduction = (old-new)/old if old>1e-8 else 0
        gate = abs(a)>=plan['minimum_fitted_coherence'] and not band['delay_at_bound'] and reduction>=plan['minimum_test_rmse_reduction_fraction']
        error = max(abs(scalar-complex(*band['scalar'])), abs(a-complex(*band['delayed_coefficient'])),
                    abs(old-band['scalar_test_rmse']), abs(new-band['delay_test_rmse']),
                    abs(reduction-band['test_rmse_reduction_fraction']))
        assert error < 1e-10 and gate == band['predictive_gate_passed'], (case['case']['name'],band_id,error)
        assert np.allclose(np.median(data['detrended_envelope_cv'][:,band_id],axis=0),
                           band['median_detrended_envelope_cv_LR'], atol=1e-14, rtol=0)
        metric_errors.append(float(error))
    observations.append(dict(name=case['case']['name'], seconds=case['case']['seconds'],
        blocks=case['blocks'], passing_bands=sum(b['predictive_gate_passed'] for b in case['bands']),
        bands=[{key:b[key] for key in ('hz','delay_seconds','fitted_coherence',
            'test_rmse_reduction_fraction','predictive_gate_passed','median_detrended_envelope_cv_LR')}
            for b in case['bands']]))

with (repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig', newline='') as stream:
    index = list(csv.DictReader(stream))
assert len(index) == 436
for row in index:
    assert sha(repo/row['文件']) == row['SHA-256'], row['文件']
assert not subprocess.check_output(['git','diff','HEAD','--','*.c','*.h'],cwd=repo).strip()
accepted = read(repo/'research/coherent_low_v1_acceptance.json')
assert sha(repo/accepted['model']) == accepted['model_sha256']
assert sha(repo/'voices/dna_bank_v1/V10 Exterior.model') == accepted['dna_model_sha256']
previous = args.workspace/'baselines/numeric_scope_v1/manifest.json'
previous_manifest = read(previous)
for row in previous_manifest['files']:
    if row['path'] == 'docs/C文件索引.csv':
        assert sha(repo/'handoff/C文件索引.csv') == row['sha256']

(args.verification/'report.json').write_text(json.dumps(dict(result='pass',
    source_sha256=sha(__file__),stereo_metric_bands=len(metric_errors),
    maximum_scalar_metric_error=max(metric_errors),c_h_count=len(index),
    c_index_sha256=sha(repo/'handoff/C文件索引.csv'),accepted_models_unchanged=True,
    limits='Same saved observations; independent arithmetic, not independent recordings or listening.'),indent=2)+'\n',encoding='utf-8')

source_paths = [Path(__file__),repo/'tools/freeze_reference_audit_v1.py',
    repo/'tools/fetch_v6_route_v1.py',repo/'tools/inspect_v6_routes_v1.py',
    repo/'tools/inspect_v6_startup_v1.py',repo/'tools/analyze_stereo_delay_v1.py',
    repo/'research/stereo_delay_v1_plan.json',
    *sorted((repo/'tools/v6_route_v1').glob('*.py')),
    *sorted((repo/'tools/stereo_delay_v1').glob('*.py'))]
summary = dict(schema='vsl.reference-audit-summary/1',date='2026-11-12',
    base_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
    result='pass',evidence_roots={k:str(v) for k,v in roots.items()},
    upstream=dict(revision=fetch['revision'],text_files=len(fetch['files']),
        text_bytes=sum(r['bytes'] for r in fetch['files']),public_entries=route['public_entries'],
        historical_loops_publicly_reachable=any(r['public_reachable'] for r in route['history']),
        startup=[{k:r[k] for k in ('profile','default_sample_start_on_starter1',
            'realistic_style_starts_samples','startup_level_default_db',
            'disconnected_starter_signal_node','sample_audio_has_style_or_starter_stop_gate')}
            for r in startup['profiles']], limits=startup['limits']+route['limits']),
    stereo=dict(known_controls=len(stereo['controls']),arithmetic_validation='pass',
        maximum_scalar_metric_error=max(metric_errors),observations=observations,
        white_noise_envelope_controls=[dict(seed=c['seed'],cv_LR=[b['median_detrended_envelope_cv_LR'] for b in c['bands']])
            for c in stereo['controls'] if c['name']=='mono'],
        promotion_decision='not_promoted',limits=stereo['limits']+[
            'Recorded CV includes ordinary band-limited beating, pitch/motion and recording transfer; not isolated engine modulation',
            'White noise already has nonzero envelope CV; no direct conversion of observed CV into extra AM depth']),
    c_h_count=len(index),c_index_sha256=sha(repo/'handoff/C文件索引.csv'),
    accepted_models_unchanged=True,prior_manifest_sha256=sha(previous),
    runtime_changes=False,new_models=False,new_state_mapping=False,human_accepted=False,
    source_sha256={p.relative_to(repo).as_posix():sha(p) for p in source_paths},
    evidence_sha256={name:{p.relative_to(root).as_posix():sha(p) for p in sorted(root.rglob('*'))
                          if p.is_file() and '__pycache__' not in p.parts} for name,root in roots.items()},
    input_metadata_sha256={name:sha(args.workspace/name) for name in
        ('references/segments_v1.json','references/approval_manifest.json')})
target = repo/'research/reference_audit_v1_summary.json'
target.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(result='pass',upstream_files=len(fetch['files']),stereo_cases=len(observations),
    passing_bands=sum(r['passing_bands'] for r in observations),
    maximum_scalar_metric_error=max(metric_errors),c_h_count=len(index))))

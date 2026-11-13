"""Freeze every generated seed/block, independent oracle, review and source provenance."""
import argparse
import shutil
import subprocess
from pathlib import Path
from research_archive_v1 import load, save, sha, freeze, verify, append_index
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace', type=Path, required=True); p.add_argument('--stage', choices=['freeze', 'verify'], required=True)
a = p.parse_args(); repo = Path(__file__).resolve().parents[1]; root = a.workspace/'baselines/idle_post_audio_v1'
if a.stage == 'verify': verify(root); print('Complete POST audio archive verified.'); raise SystemExit
evidence = a.workspace/'references/analysis/idle_post_audio_v1'
observed = load(evidence/'render1/report.json'); audit = load(evidence/'audit1/report.json')
review = load(evidence/'review1/report.json'); plot = load(evidence/'plot1/report.json')
assert observed['result'] == 'finite_POST_idle_audio_pending_listening'
assert audit['result'] == 'passed' and audit['complete_buses'] == 18 and audit['baseline_all12_buses_exact']
assert review['result'] == 'single_player_POST_idle_review' and len(review['clips']) == 20
assert plot['result'] == 'all38_finite_audio_curves_plotted' and len(plot['images']) == 2
for row in [audit, review, plot]: assert row['input_report_sha256'] == sha(evidence/'render1/report.json')
for row in [review, plot]: assert row['audit_sha256'] == sha(evidence/'audit1/report.json')
assert len(observed['renders']) == 9 and len(observed['observations']) == 38 and audit['all_curve_values'] == 32400
assert not any(row['listening_accepted'] for row in [observed, audit, review])
for row in observed['renders']:
    for bus in row['buses'].values(): assert sha(evidence/'render1'/bus['file']) == bus['sha256'] and bus['peak'] < 1.
for row in observed['observations']: assert sha(evidence/'render1'/row['file']) == row['sha256']
for row in review['clips']: assert sha(evidence/'review1'/(row['key']+'.wav')) == row['sha256']
assert sha(evidence/'plot1/metrics.json') == plot['metrics_sha256']
sources = set()
for name, digest in observed['sources'].items():
    assert sha(repo/name) == digest == sha(evidence/'render1/exact_sources'/name); sources.add(name)
for directory, source, executed in [('audit1', 'audit_idle_post_audio_v1.py', 'executed_auditor.py'),
    ('audit1', 'idle_post_audio_v1/independent.py', 'executed_independent.py'),
    ('review1', 'review_idle_post_audio_v1.py', 'executed_review.py'),
    ('review1', 'idle_post_audio_v1/review.html', 'executed_template.html'),
    ('plot1', 'plot_idle_post_audio_v1.py', 'executed_plot.py')]:
    assert sha(repo/'tools'/source) == sha(evidence/directory/executed); sources.add('tools/'+source)
for row in plot['images']:
    assert sha(evidence/'plot1'/row['file']) == row['sha256']
    name = 'research/idle_post_audio_v1_'+row['file']; shutil.copy2(evidence/'plot1'/row['file'], repo/name); sources.add(name)
sources.update(['tools/package_idle_post_audio_v1.py', 'research/怠速细节关联试听V1.md',
                'AGENTS.md', 'handoff/研究续接.md', 'handoff/开发留痕.md'])
inputs = dict(data_workspace_AGENTS=a.workspace/'AGENTS.md'); tables = {}
for name, digest in observed['parent_manifests'].items():
    path = a.workspace/'baselines'/name/'manifest.json'; assert sha(path) == digest
    inputs[name+'_manifest.json'] = path; tables[name] = {z['path']: z['sha256'] for z in load(path)['files']}
for path, digest in observed['inputs'].items():
    rel = Path(path).resolve().relative_to((a.workspace/'baselines').resolve())
    assert sha(path) == digest == tables[rel.parts[0]][Path(*rel.parts[1:]).as_posix()]
for name, count in [('C_files_sha256.json', 612), ('voice_files_sha256.json', 67)]:
    path = a.workspace/'baselines/idle_microtexture_c_v1/inputs'/name; entries = load(path); assert len(entries) == count
    for source, digest in entries.items(): assert sha(repo/source) == digest, source
    inputs[name] = path
validation = dict(schema='vsl.idle-post-audio-freeze/1', result='audited_finite_audio_pending_listening',
    parent_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip(), audit=audit,
    all3seeds_all4blocks_all81lags=True, original48000warmup=True, no_source_PCM_timeline=True,
    theory_lag_qualified=False, listening_accepted=False, source_level_identity_claim=False,
    all_figures_viewed=True, review_gain=review['common_gain'], review_url=review['url'],
    review_browser_open_request='queued', UI_interaction_or_hearing_verified=False,
    unchanged_C_H=612, unchanged_old_voices=67, runtime_changed=False, old_driving_tests_repeated=False,
    next='Use qualified offline listening candidate before C promotion; retain crossband/HF gaps and pending old pages. Do not repeat hearing question or blind-tune white jointfamilies. Original commonphase/full goal remain active.')
result = freeze(root, repo, sorted(sources), evidence, inputs, validation); verify(root)
save(repo/'research/idle_post_audio_v1_summary.json', dict(validation, **result))
append_index(repo/'handoff/阶段索引.csv', ['idle_post_audio_v1', 'baselines/idle_post_audio_v1/manifest.json', result['file_count'], result['manifest_sha256'],
    '3seeds4blocks18buses;independentRNG/fullFFT/15partition/32400points;12oldbusesexact;20samegainHTTP',
    'Finitecandidate/notaccepted/theorylagopen;612C-H67voicesunchanged',
    'research/怠速细节关联试听V1.md | research/idle_post_audio_v1_summary.json', 'baselines/idle_post_audio_v1/validation.json'])
print(result)

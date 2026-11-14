"""Verify all conditional-mean summaries and archive exact inputs without voice promotion."""
import argparse
import csv
import os
import shutil
import subprocess
import sys
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace', type=Path, required=True)
parser.add_argument('--stage', choices=['freeze', 'verify'], required=True)
args = parser.parse_args()
repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(args.workspace / 'tools/python_deps'))
for key in ['OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'OMP_NUM_THREADS']:
    os.environ[key] = '2'
import numpy as np
from research_archive_v1 import load, save, sha, freeze, verify, append_index

root = args.workspace / 'baselines/accel_upper_conditional_v1'
if args.stage == 'verify':
    print(verify(root)['file_count'])
    raise SystemExit

evidence = args.workspace / 'references/analysis/accel_upper_conditional_v1'
run = load(evidence / 'observe1/report.json')
audit = load(evidence / 'audit1/report.json')
assessment = load(evidence / 'assessment1/report.json')
assert run['result'] == 'all12_fixed_gain_conditional_means_complete'
assert len(run['observations']) == 12 and run['blocks'] == 288
assert not run['new_generation_seeds'] and not run['new_listening_audio']
assert run['conditional_mean_not_variance_qualification'] and run['only_zero_lag_diagonal'] and run['pre_refilter_only']
assert audit['result'] == 'passed' and audit['cases'] == 12 and audit['blocks'] == 288
assert audit['native_window_quadratics'] == 437760
assert audit['all1152coordinate_blocks'] and audit['all_existing_gain_histories']
assert audit['all_conditional_means_and_decompositions'] and audit['conditional_mean_not_VarS_qualification']
assert audit['only_pre_refilter_zero_lag_diagonal'] and not audit['new_audio']
assert assessment['result'] == 'all12_fixed_gain_conditional_means_assessed_NOT_variance_or_voice'
assert len(assessment['cases']) == 12 and len(assessment['figures']) == 2
assert assessment['conditional_mean_not_VarS_qualification'] and assessment['not_independent_variance_components']
assert not assessment['new_audio']
assert audit['input_sha256'] == assessment['input_sha256'] == sha(evidence / 'observe1/report.json')
assert assessment['audit_sha256'] == sha(evidence / 'audit1/report.json')
assert sha(evidence / 'observe1/known.npz') == run['known_sha256']
sources = set(run['sources'])
for name, digest in run['sources'].items():
    assert sha(repo / name) == digest == sha(evidence / 'observe1/exact_sources' / name)
parent = args.workspace / 'baselines/accel_upper_realization_v1'
assert sha(parent / 'manifest.json') == run['parent_manifest_sha256']
inputs = {'parent_manifest': parent / 'manifest.json'}
parent_table = {v['path']: v['sha256'] for v in load(parent / 'manifest.json')['files']}
for name, digest in run['parent_files'].items():
    assert sha(parent / name) == digest == parent_table[name]
    inputs['parent/' + name] = parent / name


def check(actual, expected):
    np.testing.assert_allclose(actual, expected, rtol=1e-12, atol=1e-14)


coordinate_blocks = 0
for row, item in zip(run['observations'], assessment['cases']):
    for key in ['segment', 'branch', 'fit_available']:
        assert row[key] == item[key]
    assert len(row['records']) == 3
    assert sha(evidence / 'observe1' / row['file']) == row['sha256']
    with np.load(evidence / 'observe1' / row['file']) as f, np.load(parent / row['model_parent_file']) as model:
        assert f['actual'].shape == f['conditional'].shape == (3, 8, 4)
        assert np.all(np.isfinite(f['actual'])) and np.all(np.isfinite(f['conditional']))
        check(f['expected'], model['prediction'][5].diagonal())
        check(f['source_target'], model['target'][5].diagonal())
        check(f['tile'], model['tile'])
        check(f['conditional'], f['path'] + f['carrier'])
        check(f['gain_path_effect'], f['conditional'] - f['expected'])
        check(f['carrier_realization_effect'], f['actual'] - f['conditional'])
        check(f['total_effect'], f['actual'] - f['expected'])
        check(f['total_effect'], f['gain_path_effect'] + f['carrier_realization_effect'])
        for i, record in enumerate(row['records']):
            name = 'evidence/generate1/' + record['observation_file']
            assert run['parent_files'][name] == record['observation_sha256'] == sha(parent / name)
            with np.load(parent / name) as old:
                check(f['actual'][i], old['raw_theoretical_normalized'][:, 5].diagonal(axis1=1, axis2=2))
            check(f['squared_gain_means'][i], record['gain_squared_mean'])
        for reported, key in [('expected', 'expected'), ('source_target', 'source_target'),
                              ('all24_actual', 'actual'), ('all24_conditional', 'conditional')]:
            check(item[reported], f[key])
        for reported, key in [('mean_actual', 'actual'), ('mean_conditional', 'conditional'),
                              ('mean_path_part', 'path'), ('mean_carrier_part', 'carrier'),
                              ('mean_gain_path_effect', 'gain_path_effect'),
                              ('mean_carrier_realization_effect', 'carrier_realization_effect'),
                              ('mean_total_effect', 'total_effect')]:
            check(item[reported], f[key].mean(axis=(0, 1)))
        for reported, key in [('run_mean_actual', 'actual'), ('run_mean_conditional', 'conditional')]:
            check(item[reported], f[key].mean(axis=1))
        check(item['minimum_conditional_carrier_part'], f['carrier'].min())
        arithmetic = abs(f['total_effect'] - f['gain_path_effect'] - f['carrier_realization_effect']).max()
        check(item['maximum_arithmetic_error'], arithmetic)
        assert arithmetic <= 1e-12
        for reported, key in [('actual_mean', 'actual'), ('conditional_mean', 'conditional'),
                              ('mean_gain_path_effect', 'gain_path_effect'),
                              ('mean_carrier_realization_effect', 'carrier_realization_effect')]:
            check(row[reported], f[key].mean(axis=(0, 1)))
        coordinate_blocks += f['actual'].size
assert coordinate_blocks == 1152
assert sum(row['branch'] == 'original' and row['fit_available'] for row in run['observations']) == 3
assert all(not row['fit_available'] for row in run['observations'] if row['branch'] != 'original')
for name, folder, snapshot in [
    ('tools/audit_accel_upper_conditional_v1.py', 'audit1', 'executed_auditor.py'),
    ('tools/assess_accel_upper_conditional_v1.py', 'assessment1', 'executed_assessment.py'),
]:
    assert sha(repo / name) == sha(evidence / folder / snapshot)
    sources.add(name)
for figure in assessment['figures']:
    path = evidence / 'assessment1' / figure['file']
    assert sha(path) == figure['sha256']
    name = 'research/accel_upper_conditional_v1_' + figure['file']
    shutil.copy2(path, repo / name)
    sources.add(name)
ch = list(csv.reader((repo / 'handoff/C文件索引.csv').open(encoding='utf-8-sig')))
assert len(ch) == 620 and all(sha(repo / row[0]) == row[4] for row in ch[1:])
voice_path = args.workspace / 'baselines/idle_microtexture_c_v1/inputs/voice_files_sha256.json'
voices = load(voice_path)
assert len(voices) == 67 and all(sha(repo / name) == digest for name, digest in voices.items())
inputs.update(C_H_index=repo / 'handoff/C文件索引.csv', voice_hashes=voice_path,
              idle_pending_manifest=args.workspace / 'baselines/idle_complex75_v1/manifest.json')
sources.update(['tools/package_accel_upper_conditional_v1.py', 'research/力度轨迹条件核查V1.md',
                'AGENTS.md', 'handoff/研究续接.md', 'handoff/开发留痕.md'])
shutil.copy2(repo / 'AGENTS.md', args.workspace / 'AGENTS.md')
validation = dict(
    schema='vsl.accel-upper-conditional-freeze/1',
    result='all_existing_conditional_means_and_signed_decompositions_verified_NOT_variance_or_voice',
    parent_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip(),
    previous_goal_turn_classification='progress:80a814c continuous source generation, all576 observations, independent full replay and localized high-order finite discrepancy',
    independent_audit=audit, cases=12, blocks=288, coordinate_blocks=coordinate_blocks,
    all_assessment_vectors_run_means_and24block_values_verified=True,
    all_consumed_parent_inputs_and_exact_executed_sources_preserved=True,
    known_controls_before_source=True, no_failed_attempts=True, figures_viewed=True,
    zero_lag_diagonal_pre_refilter_only=True, conditional_mean_not_VarS_qualification=True,
    not_independent_variance_components=True, no_mechanical_or_causal_attribution=True,
    full11lag_variance_and_refilter_fourth_moments_not_qualified=True,
    all_source_cases=[row for row in assessment['cases'] if row['branch'] == 'original'],
    unavailable_controls_diagnostic_only=True, old619C_H_and67voices_exact=True,
    moving35_changed=False, runtime_changed=False, pending_idle_listening_unchanged=True,
    new_seeds=False, new_listening_audio=False, new_runtime_profile=False, new_C=False,
    new_download=False, old_CTests_repeated=False, full_MSC_original_gate_still_unpassed=True,
    original_common_phase_qualification_unwaived=True, next=assessment['next'], full_goal_complete=False,
)
result = freeze(root, repo, sources, evidence, inputs, validation)
verify(root)
save(repo / 'research/accel_upper_conditional_v1_summary.json', dict(validation, **result))
append_index(repo / 'handoff/阶段索引.csv', [
    'accel_upper_conditional_v1', 'baselines/accel_upper_conditional_v1/manifest.json',
    result['file_count'], result['manifest_sha256'],
    '12models288blocks1152coords;fixedGainConditionalMean;fullIndependentContractions',
    'zeroLagDiagonalPreRefilterONLY;NOTvarianceComponentsOrVarS;619C-H67voices',
    'research/力度轨迹条件核查V1.md | research/accel_upper_conditional_v1_summary.json',
    'baselines/accel_upper_conditional_v1/validation.json',
])
print(result)

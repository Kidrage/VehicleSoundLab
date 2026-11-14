"""Index and freeze the optional additive F3 catalog integration and all evidence."""
import argparse
import csv
import io
from pathlib import Path
import shutil
import subprocess
import xml.etree.ElementTree as ET
from research_archive_v1 import load, save, sha, freeze, verify, append_index

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace', type=Path, required=True)
p.add_argument('--stage', choices=['index', 'freeze', 'verify'], required=True)
a = p.parse_args()
repo = Path(__file__).resolve().parents[1]
e = a.workspace / 'references/analysis/catalog_F3_v1'
root = a.workspace / 'baselines/catalog_F3_v1'
build = repo / 'build-catalog-F3-v1'
if a.stage == 'verify':
    verify(root)
    print('F3 catalog archive verified')
    raise SystemExit
before = load(e / 'before_C_files_sha256.json')
voices = load(e / 'before_voice_files_sha256.json')
names = subprocess.check_output(['git', 'ls-files', '-z'], cwd=repo).decode('utf-8').split('\0')
names += subprocess.check_output(['git', 'ls-files', '--others', '--exclude-standard', '-z'], cwd=repo).decode('utf-8').split('\0')
names = sorted(set(n for n in names if n))
current = {n: sha(repo / n) for n in names if Path(n).suffix in ('.c', '.h')}
changed = {n for n in before if current[n] != before[n]}
added = {'experiments/catalog_drive_v1/F3_models.c', 'experiments/catalog_drive_v1/F3_models.h',
         'experiments/catalog_drive_v1/F3_checks.c'}
assert len(before) == 647 and len(current) == 650 and set(current) - set(before) == added
assert changed == {'modules/drive_recipe/bank.c', 'modules/drive_catalog/catalog.c', 'modules/drive_catalog/catalog.h',
                   'experiments/catalog_drive_v1/models.c', 'experiments/catalog_drive_v1/contract.c',
                   'experiments/catalog_drive_v1/ui_checks.c'}
assert len(voices) == 74 and all(sha(repo / n) == h for n, h in voices.items())
f2 = ['experiments/modal_idle_v1/F2_fixed_idle.msource', 'experiments/modal_texture_v1/F2_amplitude.mtexture',
      'experiments/spectral_texture_v1/F2_fine_static.sfir']
for n in f2:
    assert sha(repo / n) == sha(a.workspace / 'baselines/F3_lift_voice_v1/source' / n)
for name, item in load(e / 'asset_provenance.json').items():
    parent = a.workspace / 'baselines' / item['parent']
    rows = {v['path']: v['sha256'] for v in load(parent / 'manifest.json')['files']}
    target = repo / 'voices/F3_before_upshift_v1' / name
    assert sha(parent / 'manifest.json') == item['parent_manifest_sha256']
    assert sha(target) == sha(parent / item['path']) == rows[item['path']] == item['sha256']
    voices[target.relative_to(repo).as_posix()] = sha(target)
index = repo / 'handoff/C文件索引.csv'
rows = list(csv.reader(index.open(encoding='utf-8-sig', newline='')))
if a.stage == 'index':
    assert len(rows) == 648 and all(row[4] == before[row[0]] for row in rows[1:])
    for row in rows[1:]:
        row[4] = current[row[0]]
    for n in sorted(added):
        role = 'F3冻结DNA与叠加双声道细节的非实时事务装载' if 'models' in n else '零撤出主DNA精确／独立细节／无LF／支持／失效事务核查'
        rows.append([n, '目录叠加配方接入', 'catalog_drive_v1', role, current[n]])
    output = io.StringIO(newline='')
    csv.writer(output, lineterminator='\n').writerows(rows)
    index.write_text(output.getvalue(), encoding='utf-8', newline='\n')
    save(e / 'C_files_sha256.json', current)
    save(e / 'voice_files_sha256.json', voices)
    print('650 C/H:6 changes,641 preserved,3 added;74 old voices exact,2 frozen F3 parameters added')
    raise SystemExit
assert len(rows) == 651 and all(row[4] == current[row[0]] for row in rows[1:])
for phase in ('focused1', 'full1', 'host1'):
    result = load(e / phase / 'report.json')
    assert result['result'] == 'passed'
    for n, h in result['sources'].items():
        assert sha(repo / n) == h == sha(e / phase / 'exact_sources' / n), (phase, n)
tests = ET.parse(e / 'full1/ctest.xml').getroot().findall('.//testcase')
assert len(tests) == 67 and all(t.find('failure') is None and t.find('error') is None for t in tests)
ui = load(e / 'host1/ui.json')
assert ui['result'] == 'pass' and ui['voices'] == 10 and len(ui['records']) == 10 and ui['cross_voice_replay_and_live_restore']
assert ui['frames_per_record'] == 64123 and ui['bench_load']['frames'] == 240123
reg = load(e / 'regress1/report.json')
assert reg['result'] == 'passed' and len(reg['old_cases']) == 9 and len(reg['new_cases']) == len(reg['crossing']) == 10
assert reg['F3_source_hash_2_12_exact'] and reg['old_render_id'] != reg['new_render_id']
assert sha(repo / 'tools/regress_catalog_F3_v1.py') == sha(e / 'regress1/executed_regression.py')
assert sha(repo / 'tools/review_catalog_F3_v1.py') == sha(e / 'review1/executed_review.py')
assert load(e / 'review1/report.json')['result'] == 'seven_native_images_ready'
assert load(e / 'review1/visual_review.json')['result'] == 'seven_own_window_images_visually_reviewed'
for k in range(10):
    assert sha(build / ('catalog-check/voice_%d.wav' % k)) == sha(e / ('regress1/new_render/voice_%d.wav' % k))
    report = load(build / ('catalog-check/voice_%d.json' % k))
    assert report['render_id'] == reg['new_render_id'] and report['frames'] == 192123
    assert report['owned_replay_PCM_exact'] and report['driver_2_12_exact'] and report['stems_2_12_exact']
for n in ('default', 'bench', 'stationary', 'decel', 'F3', 'replay', 'restored'):
    assert (e / 'review1' / (n + '.png')).is_file()
assert load(e / 'prepare1_failure.json')['original_C_modified'] is False
binary = e / 'bin'
binary.mkdir(exist_ok=False)
for n in ('VslAtlasMonitor', 'VslAtlasTake_render', 'catalog_contract_checks', 'catalog_render_checks',
          'catalog_recipe_checks', 'catalog_F3_checks'):
    shutil.copy2(build / ('bin/Release/' + n + '.exe'), binary / (n + '.exe'))
sources = [n for n in names if Path(n).suffix in ('.c', '.h', '.cmake', '.in') or n.endswith('CMakeLists.txt')]
sources += list(voices) + f2 + ['voices/F3_before_upshift_v1/index.json', 'modules/drive_recipe/README.md',
    'modules/drive_catalog/README.md', 'tools/build_catalog_drive_v1.py', 'tools/regress_catalog_F3_v1.py',
    'tools/review_catalog_F3_v1.py', 'tools/package_catalog_F3_v1.py', 'tools/research_archive_v1.py',
    'research/catalog_F3_v1_plan.json', 'research/F3叠加细节接入统一窗口V1.md', 'Build-Voice-Catalog.ps1',
    'Launch-Voice-Catalog.cmd', 'README.md', 'AGENTS.md', 'handoff/C文件索引.csv', 'handoff/C模块与接口.md',
    'handoff/算法说明.md', 'handoff/研究续接.md', 'handoff/开发留痕.md', 'handoff/当前代码阅读入口.md',
    'research/怠速优化当前状态.md', 'research/E_decel_source_v1_listening.json']
validation = dict(result='optional_F3_additive_stereo_recipe_in_shared_catalog',
    git_parent=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo).decode().strip(),
    previous_goal_turn='progress: requested source-bound MCPS recomputation completed; synthesis unchanged and F3 integration remained the next safe action',
    C_H_total=650, C_H_changed=6, C_H_prior_exact=641, C_H_added=3, original_voice_parameters_exact=74,
    new_parameters_exact_frozen_copies=2, total_voice_parameters=76, F2_exact=True,
    changed_C_H=sorted(changed), DSP_change='generic validation accepts active additive detail; no generation tick changes',
    presets=10, V10_contexts=8, analytic_examples=2, new_real_engines=0, source_refit=False,
    new_timbre_accepted=False, default_selection_changed=False, pending_idle_migrated=False,
    F3_hearing='independently pending; no repeated question or strength change',
    E_feedback='左右关系有改善，音色仍明显电子',
    automatic_state_mapping_added=False, full_RPM_load_calibration=False, room_added=False,
    config_seed=48271, DNA_seed=48271, detail_seed=8121907, offline_DNA_seed=1,
    offline_mixed_audition_byte_identity_claimed=False, harmonic_withdrawal=0, independent_LF=False,
    distinct_CTests=67, native_UI=ui, images_visually_reviewed=7, manual_mouse_verified=False,
    actual_render_frames_per_preset=192123, original_nine_WAV_exact=True,
    frozen_old_player_old_nine_exact=True, new_player_new_ten_exact=True, strict_cross_renderer_rejection=True,
    render_id_before=reg['old_render_id'], render_id_after=reg['new_render_id'],
    source_driver_and_dry_stems_2_12_exact=True, owned_irregular_block_replay_exact=True,
    take_schema=10, take_controls=32, native_bench_replay_exact=True,
    old_live_windows_and_builds_preserved=True, preparation_failure_preserved=True,
    failed_build_test_attempts=[], downloaded=False, pushed=False, hard_realtime_claim=False,
    physical_7_1_4_verified=False, full_goal='active',
    next='Independent state/RPM/load and additional real-engine evidence plus pending human hearings. '
         'Do not reparameterize unsupported F3 cyclic or boundary-limited event timing, blind-tune idle, or treat catalog count as engine coverage.')
inputs = {'before_C_files_sha256.json': e / 'before_C_files_sha256.json', 'C_files_sha256.json': e / 'C_files_sha256.json',
    'before_voice_files_sha256.json': e / 'before_voice_files_sha256.json', 'voice_files_sha256.json': e / 'voice_files_sha256.json',
    'F3_DNA_manifest.json': a.workspace / 'baselines/F3_lift_voice_v1/manifest.json',
    'F3_detail_manifest.json': a.workspace / 'baselines/F3_detail_v1/manifest.json',
    'F3_transient_manifest.json': a.workspace / 'baselines/F3_shift_transient_v1/manifest.json',
    'prior_catalog_manifest.json': a.workspace / 'baselines/catalog_decel_v1/manifest.json',
    'data_AGENTS.md': a.workspace / 'AGENTS.md'}
result = freeze(root, repo, sources, e, inputs, validation)
verify(root)
save(repo / 'research/catalog_F3_v1_summary.json', dict(validation, **result))
append_index(repo / 'handoff/阶段索引.csv', ['catalog_F3_v1', 'baselines/catalog_F3_v1/manifest.json',
    result['file_count'], result['manifest_sha256'],
    '10optional recipes;67CTest;9old WAV exact;10owned replay;strict identities;2/12 dry sources;native muted controls',
    'F3 additive zero withdrawal/no LF;74old voices/F2 exact;no new listening/state/physical7.1.4 qualification',
    'research/F3叠加细节接入统一窗口V1.md | research/catalog_F3_v1_summary.json', 'baselines/catalog_F3_v1/validation.json'])
print(result)

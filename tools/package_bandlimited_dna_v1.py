"""Index and freeze opt-in carrier-safe loading, checks and old-byte evidence."""
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
e = a.workspace/'references/analysis/bandlimited_dna_v1'
root = a.workspace/'baselines/bandlimited_dna_v1'
prior = a.workspace/'baselines/catalog_F3_v1'
if a.stage == 'verify':
    result = verify(root)
    print('PASS frozen archive', result['file_count'], result['bytes'])
    raise SystemExit
before = load(prior/'inputs/C_files_sha256.json')
voices = load(prior/'inputs/voice_files_sha256.json')
names = set()
for switches in (['ls-files', '-z'], ['ls-files', '--others', '--exclude-standard', '-z']):
    names.update(subprocess.check_output(['git']+switches, cwd=repo).decode('utf-8').split('\0'))
names.discard('')
current = {n: sha(repo/n) for n in sorted(names) if Path(n).suffix in ('.c', '.h')}
expected_changed = {'modules/sound_dna/profile.c', 'modules/sound_dna/profile.h',
                    'modules/dna_atlas/bank.c', 'modules/dna_atlas/bank.h'}
expected_added = {'experiments/bandlimited_dna_v1/'+n for n in
                  ['test_models.c', 'test_models.h', 'load_checks.c', 'render_checks.c', 'drive_checks.c', 'probe.c']}
changed = {n for n, h in before.items() if current[n] != h}
assert len(before) == 650 and len(current) == 656
assert changed == expected_changed and set(current)-set(before) == expected_added
assert len(voices) == 76 and all(sha(repo/n) == h for n, h in voices.items())
f2 = ['experiments/modal_idle_v1/F2_fixed_idle.msource',
      'experiments/modal_texture_v1/F2_amplitude.mtexture', 'experiments/spectral_texture_v1/F2_fine_static.sfir']
assert all(sha(repo/n) == sha(prior/'source'/n) for n in f2)
index = repo/'handoff/C文件索引.csv'
rows = list(csv.reader(index.open(encoding='utf-8-sig', newline='')))
if a.stage == 'index':
    assert len(rows) == 651 and all(row[4] == before[row[0]] for row in rows[1:])
    for row in rows[1:]:
        row[4] = current[row[0]]
        if row[0] in expected_changed:
            row[3] += '；明确选用的较高根频率带限装载／原安全接口保持'
    roles = {'test_models.c': '已知复数声线与随机纹理测试参数，非实录／RPM',
             'test_models.h': '共用测试参数接口与断言', 'load_checks.c': '完整系数／高阶／旧保护／失败事务检查',
             'render_checks.c': '解析载波与左右相位／连续扫频／旧字节／分块状态检查',
             'drive_checks.c': '同驾驶器高锚点与2-12干声精确／owned边界检查',
             'probe.c': '显式绝对根频率／seed／块长的非实时原SaVoice导出'}
    for n in sorted(expected_added):
        rows.append([n, '带限DNA明确选用接入', 'bandlimited_dna_v1', roles[Path(n).name], current[n]])
    stream = io.StringIO(newline='');csv.writer(stream, lineterminator='\n').writerows(rows)
    index.write_text(stream.getvalue(), encoding='utf-8', newline='\n')
    for label, value in [('before_C_files_sha256', before), ('C_files_sha256', current),
                         ('voice_files_sha256', voices)]:
        save(e/(label+'.json'), value)
    print('PASS656 C/H:646 preserved,4 nonRT changes,6 added;76 voices/F2 exact')
    raise SystemExit
assert len(rows) == 657 and all(row[4] == current[row[0]] for row in rows[1:])
for phase in ('focused1', 'full1'):
    result = load(e/phase/'report.json')
    assert result['result'] == 'passed'
    for n, h in result['sources'].items():
        assert sha(repo/n) == h == sha(e/phase/'exact_sources'/n), (phase, n)
tests = ET.parse(e/'full1/ctest.xml').getroot().findall('.//testcase')
assert len(tests) == 70 and all(t.find('failure') is None and t.find('error') is None and t.find('skipped') is None for t in tests)
export = load(e/'export1/report.json');catalog = load(e/'catalog1/report.json')
assert export['result'] == catalog['result'] == 'passed'
assert export['legacy_raw_exact'] and export['block_37_512_exact'] and export['invalid_before_output'] == 8
assert len(catalog['catalog']) == 10 and catalog['strict_cross_identity_rejections'] == 4
assert catalog['old_render_id'] == 'ffaa827e1c325f2f46a9055632856a6975c4d88e81d5b3beb62d4e6daa925497'
assert catalog['new_render_id'] != catalog['old_render_id']
assert catalog['schema'] == 10 and catalog['controls'] == 32
for phase in ('export1', 'catalog1'):
    assert sha(repo/'tools/verify_bandlimited_dna_v1.py') == sha(e/phase/'executed_verify.py')
shutil.copy2(__file__, e/'executed_package.py')
binary = e/'bin';binary.mkdir(exist_ok=False)
for n in ['bandlimited_load_checks', 'bandlimited_render_checks', 'bandlimited_drive_checks',
          'sound_dna_bandlimited_export', 'sound_dna_legacy_export', 'VslAtlasTake_render']:
    shutil.copy2(repo/('build-bandlimited-dna-v1/bin/Release/'+n+'.exe'), binary/(n+'.exe'))
shutil.copy2(prior/'evidence/bin/VslAtlasTake_render.exe', binary/'frozen_old_player.exe')
shutil.copy2(repo/'build-sound-dna-export-v1/bin/Release/sound_dna_export.exe', binary/'frozen_old_raw_export.exe')
validation = dict(result='opt_in_high_root_profile_and_atlas_loading_verified',
    git_parent=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip(),
    previous_goal_turn='No synthesis progress: MCPS recheck only confirmed unchanged inputs/costs. Identified high-root loader work resumed.',
    C_H_total=656, C_H_prior_exact=646, C_H_changed=4, C_H_added=6,
    changed_C_H=sorted(changed), added_C_H=sorted(expected_added),
    voices_exact=76, F2_exact=True, original_guard_retained=True,
    opt_in_base_hz=[5,1000], max_harmonics=320,
    actual_root_renderer='existing SaVoice carrier taper19200..21600Hz; no DSP tick changes',
    legacy_layouts_unchanged=True, high_root_direct_driver_2_12_exact=True,
    stochastic_sideband_brickwall_claim=False, measured_source_RPM_claim=False,
    focused_checks=3, complete_CTests=70, inherited_CTests=67,
    analytic_exports=export['analytic'], block_37_512_exact=True, invalid_before_output=8,
    legacy_raw_WAV_exact=True, old_compatible_bank_and_state_exact=True,
    ten_catalog_WAV_exact=True, ten_old_and_new_owned_replays_exact=True,
    strict_cross_identity_rejections=4, old_render_id=catalog['old_render_id'],
    new_render_id=catalog['new_render_id'], take_schema=10, take_controls=32,
    high_root_owned_support=False, high_root_UI_added=False, live_default_changed=False,
    new_source_refit=False, new_timbre_acceptance=False, room_added=False,
    F2_and_F3_hearings='independently pending; no repeated question, strength changes or migration',
    E_feedback='左右关系有改善，音色仍明显电子',
    physical_7_1_4_verified=False, hard_realtime_claim=False, optimized_ADI_port=False,
    failed_executed_tests=[], existing_build_warning='C4127 catalog_drive_v1/ui_checks.c constant condition; unchanged',
    downloaded=False, pushed=False, full_goal='active',
    next='Independent higher-root evidence in approved media, then existing extraction checks; '
         'versioned owned/live integration still needed. No failed-window/gate rescue or extrapolation-as-coverage.')
sources = sorted(n for n in names if Path(n).suffix in ('.c', '.h', '.cmake', '.in') or n.endswith('CMakeLists.txt'))
sources += list(voices)+f2+[
    'tools/build_bandlimited_dna_v1.py', 'tools/verify_bandlimited_dna_v1.py',
    'tools/package_bandlimited_dna_v1.py', 'tools/research_archive_v1.py',
    'research/bandlimited_dna_v1_plan.json', 'research/带限DNA接入V1.md',
    'experiments/bandlimited_dna_v1/README.md', 'modules/sound_dna/README.md', 'modules/dna_atlas/README.md',
    'README.md', 'AGENTS.md', 'handoff/C文件索引.csv', 'handoff/C模块与接口.md',
    'handoff/算法说明.md', 'handoff/当前代码阅读入口.md', 'handoff/研究续接.md', 'handoff/开发留痕.md']
inputs = {'before_C_files_sha256.json': e/'before_C_files_sha256.json',
          'C_files_sha256.json': e/'C_files_sha256.json', 'voice_files_sha256.json': e/'voice_files_sha256.json',
          'prior_catalog_manifest.json': prior/'manifest.json',
          'prior_numeric_manifest.json': a.workspace/'baselines/residual_ratio_numeric_v1/manifest.json',
          'data_AGENTS.md': a.workspace/'AGENTS.md'}
result = freeze(root, repo, sources, e, inputs, validation)
verify(root)
save(repo/'research/bandlimited_dna_v1_summary.json', dict(validation, **result))
append_index(repo/'handoff/阶段索引.csv', ['bandlimited_dna_v1', 'baselines/bandlimited_dna_v1/manifest.json',
    result['file_count'], result['manifest_sha256'],
    '70CTest;known high-order/sweep/stereo;old raw+10catalog WAV exact;20owned replays;strict identity;2/12dry',
    '656C-H:4nonRT changes6new;76voices/F2 exact;no live highroot/owned migration/listening/source refit',
    'research/带限DNA接入V1.md | research/bandlimited_dna_v1_summary.json', 'baselines/bandlimited_dna_v1/validation.json'])
print('PASS frozen', result)

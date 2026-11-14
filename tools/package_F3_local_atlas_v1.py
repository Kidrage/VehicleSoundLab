"""Index new offline C adapters and freeze both local banks with all attempts."""
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
p.add_argument('--stage', choices=('index', 'freeze', 'verify'), required=True)
a = p.parse_args()
repo = Path(__file__).resolve().parents[1]
e = a.workspace/'references/analysis/F3_local_atlas_v1'
root = a.workspace/'baselines/F3_local_atlas_v1'
if a.stage == 'verify':
    m = verify(root)
    print(dict(result='archive_verified', files=m['file_count'], bytes=m['bytes']))
    raise SystemExit
parent = a.workspace/'baselines/bandlimited_dna_v1'
old = load(parent/'inputs/C_files_sha256.json')
voices = load(parent/'inputs/voice_files_sha256.json')
assert len(old) == 656 and len(voices) == 76
assert all(sha(repo/n) == h for n, h in {**old, **voices}.items())
names = set()
for flags in (['ls-files', '-z'], ['ls-files', '--others', '--exclude-standard', '-z']):
    names.update(subprocess.check_output(['git']+flags, cwd=repo).decode('utf-8').split('\0'))
names.discard('')
current = {n: sha(repo/n) for n in sorted(names) if Path(n).suffix in ('.c', '.h')}
roles = {'assets.c': '事务加载UTF8模型清单／拥有参数并绑定原SaBank',
         'assets.h': '离线模型拥有权与原SaBank接口', 'schedule.c': '有界有序控制轨迹的非实时事务读取',
         'schedule.h': '预验证轨迹事件与容量契约', 'input.h': '严格有界无符号整数读取／拒绝符号溢出',
         'probe.c': '原SaVoice逐事件分块导出／FLOAT波形与遥测',
         'checks.c': '模型与轨迹失败事务／bank借用指针检查',
         'driver_checks.c': '原唯一驾驶器2-12声源／六干声总线／状态精确检查'}
added = {'experiments/local_atlas_v1/'+n for n in roles}
assert len(current) == 664 and set(current)-set(old) == added
f2 = ['experiments/modal_idle_v1/F2_fixed_idle.msource',
      'experiments/modal_texture_v1/F2_amplitude.mtexture',
      'experiments/spectral_texture_v1/F2_fine_static.sfir']
assert all(sha(repo/n) == sha(parent/'source'/n) for n in f2)
index = repo/'handoff/C文件索引.csv'
rows = list(csv.reader(index.open(encoding='utf-8-sig', newline='')))
if a.stage == 'index':
    assert len(rows) == 657 and all(row[4] == old[row[0]] for row in rows[1:])
    for n in sorted(added):
        rows.append([n, '局部多锚点离线入口', 'local_atlas_v1', roles[Path(n).name], current[n]])
    stream = io.StringIO(newline='')
    csv.writer(stream, lineterminator='\n').writerows(rows)
    index.write_text(stream.getvalue(), encoding='utf-8', newline='\n')
    for label, value in [('C_files_sha256.json', current), ('voice_files_sha256.json', voices)]:
        save(e/label, value)
    print('PASS664 C/H:656prior exact+8offline adapters;76voices/F2 exact')
    raise SystemExit
assert len(rows) == 665 and all(row[4] == current[row[0]] for row in rows[1:])
bad = load(e/'build1/report.json')
assert bad['result'] == 'failed' and b'DirectoryNotFoundException' in (e/'build1/command1.log').read_bytes()
for n, h in bad['sources'].items():
    assert sha(e/'build1/exact_sources'/n) == h
build = load(e/'build2/report.json')
known = load(e/'known1/report.json')
source = load(e/'source1/report.json')
audit = load(e/'audit1/report.json')
review = load(e/'review1/report.json')
browser = load(e/'browser1/report.json')
assert build['result'] == 'passed' and build['focused_CTests'] == 2
tests = ET.parse(e/'build2/ctest.xml').getroot().findall('.//testcase')
assert len(tests) == 2 and all(t.find('failure') is None and t.find('error') is None and t.find('skipped') is None for t in tests)
assert known['result'] == 'known_analytic_alignment_rejections_and_overwrite_passed'
assert known['full_analytic_error_FS'] < 3e-7 and known['overwrite_preserved']
assert source['result'] == 'two_separate_frozen_triplets_rendered' and source['C_audio_files'] == 12
assert all(v['block_37_512_audio_and_trace_exact'] for v in source['banks'])
assert audit['result'] == 'two_local_atlas_dynamic_clocks_alignment_and_sparse_C_verified'
assert all(len(v['sparse_indices']) == 80 and len(v['renders']) == 6 for v in audit['banks'])
assert review['result'] == 'two_local_atlas_one_player_review_ready' and len(review['clips']) == 12
assert browser['result'] == 'passed' and browser['reference_link'] and not browser['hearing']
assert sha(repo/'tools/check_F3_local_atlas_v1.cjs') == sha(e/'browser1/executed_check.cjs')
sources = set(current) | set(voices) | set(f2)
sources.update(n for n in names if Path(n).suffix in ('.cmake', '.in') or n.endswith('CMakeLists.txt'))
for phase in ('build2', 'known1', 'source1', 'audit1', 'review1'):
    r = load(e/phase/'report.json')
    for n, h in r['sources'].items():
        assert sha(repo/n) == h == sha(e/phase/'exact_sources'/n), (phase, n)
        sources.add(n)
    for n, h in r.get('inputs', {}).items():
        assert sha(Path(n)) == h, (phase, n)
    for command in r.get('commands', []):
        if 'binary_sha256' in command:
            assert sha(Path(command['argv'][0])) == command['binary_sha256']
sources.update(['tools/package_F3_local_atlas_v1.py', 'tools/check_F3_local_atlas_v1.cjs',
    'tools/research_archive_v1.py', 'experiments/local_atlas_v1/README.md',
    'research/F3连续局部声纹库V1.md', 'research/F3_local_atlas_v1_plan.json',
    'README.md', 'AGENTS.md', 'handoff/C文件索引.csv', 'handoff/C模块与接口.md',
    'handoff/开发留痕.md', 'handoff/研究续接.md', 'handoff/当前代码阅读入口.md'])
validation = dict(
    result='two_separate_controllable_local_atlases_verified_and_frozen',
    git_parent=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip(),
    previous_goal_turn='Progress: five fixed local observations, same-root comparison, one-player review and complete evidence frozen in722ce4f.',
    separate_banks=[dict(name=v['name'], roots=v['root_hz'], model_paths=v['models']) for v in source['banks']],
    source_refit=False, alignment_orders=32, inherited_harmonics=288, inherited_components=12,
    shared_DSP_or_driver_changed=False, C_H_total=664, C_H_prior_exact=656, C_H_added=8,
    voices_exact=76, F2_exact=True, focused_CTests=2, original_70CTest_not_repeated=True,
    known_full_wave_error_FS=known['full_analytic_error_FS'], invalid_checks=known['invalid_before_output'],
    known_transactional_inputs_and_overwrite=True, C_audio_files=12, seconds_per_file=12,
    block_37_512_extra_files=2, block_audio_and_trace_exact=True,
    real_and_known_original_driver_2_12_cases=3, driver_frames_per_case=240123,
    original_driver_raw_six_buses_and_state_exact=True, every_render_has_one_driver_clock=True,
    independent_alignment_and_dynamic_C_audit=audit, sparse_points_per_file=80,
    whole_stochastic_wave_oracle=False, listener_files=12, common_gain=.5, fade_frames=240,
    browser=browser, screenshots_viewed=3, diagnostic_plot_viewed=True, human_hearing=False,
    failures_preserved=['build1 Windows nested path DirectoryNotFoundException;build2 shortens only new CMake binary subtree'],
    live_catalog_defaults_or_take_changed=False, high_root_owned_live_support=False,
    new_timbre_accepted=False, state_RPM_load_calibrated=False, new_real_engine_families=False,
    F2_F3_hearings='independently pending; no repeat/blind strengths/migration',
    E_feedback='左右关系有改善，音色仍明显电子',
    physical_7_1_4=False, target_ADI_port_or_WCET=False, new_download=False, pushed=False,
    full_goal='active', next='Optional explicit local-range native catalog/owned/take integration with original driver and frozen defaults; continue high-frequency/states/other real engines/physical7.1.4.')
binary = e/'bin'
binary.mkdir(exist_ok=False)
for n in ('local_atlas_export', 'local_atlas_checks', 'local_atlas_driver_checks'):
    shutil.copy2(repo/('build-local-atlas-v1/bin/Release/'+n+'.exe'), binary/(n+'.exe'))
shutil.copy2(__file__, e/'executed_package.py')
inputs = {'C_files_sha256.json': e/'C_files_sha256.json',
          'voice_files_sha256.json': e/'voice_files_sha256.json',
          'before_C_files_sha256.json': parent/'inputs/C_files_sha256.json',
          'prior_bandlimited_manifest.json': parent/'manifest.json',
          'prior_pitch_manifest.json': a.workspace/'baselines/F3_pitch_anchors_v1/manifest.json',
          'prior_fifth_manifest.json': a.workspace/'baselines/F3_fifth_voice_v1/manifest.json',
          'data_AGENTS.md': a.workspace/'AGENTS.md'}
# Bind all six exact frozen parameter bytes as portable explicit inputs too.
for i, bank in enumerate(source['banks'], 1):
    for j, path in enumerate(bank['models'], 1):
        inputs['models/bank%d_anchor%d.model' % (i, j)] = Path(path)
result = freeze(root, repo, sources, e, inputs, validation)
verify(root)
save(repo/'research/F3_local_atlas_v1_summary.json', dict(validation, **result))
append_index(repo/'handoff/阶段索引.csv', [
    'F3_local_atlas_v1', 'baselines/F3_local_atlas_v1/manifest.json', result['file_count'], result['manifest_sha256'],
    '2separate triplets;2focusedCTest;known576k analytic;12x80dynamic C;37/512exact;3known-real2/12driver checks;12clipreview',
    '664C-H:656prior exact8offline;76voices/F2 exact;build1path failure kept;local only/no live/hearing promotion',
    'research/F3连续局部声纹库V1.md | research/F3_local_atlas_v1_summary.json',
    'baselines/F3_local_atlas_v1/validation.json'])
print(result)

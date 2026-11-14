"""Index and freeze the two optional local F3 native catalog entries."""
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
e = a.workspace/'references/analysis/catalog_local_F3_v1'
root = a.workspace/'baselines/catalog_local_F3_v1'
if a.stage == 'verify':
    m = verify(root)
    print(dict(result='archive_verified', files=m['file_count'], bytes=m['bytes']))
    raise SystemExit
before = load(e/'before_C_files_sha256.json')
voices = load(e/'before_voice_files_sha256.json')
assert len(before) == 664 and len(voices) == 76
names = set()
for flags in (['ls-files', '-z'], ['ls-files', '--others', '--exclude-standard', '-z']):
    names.update(subprocess.check_output(['git']+flags, cwd=repo).decode('utf-8').split('\0'))
names.discard('')
current = {n: sha(repo/n) for n in sorted(names) if Path(n).suffix in ('.c', '.h')}
changed = {n for n in before if current[n] != before[n]}
roles = {'F3_local_models.c': '两独立F3局部库非实时事务装载与参数拥有权',
         'F3_local_models.h': '三模型拥有对象与两观察组装配接口',
         'F3_local_checks.c': '拥有权销毁/全240123帧源契约/同驾驶器2-12干声检查'}
added = {'experiments/catalog_drive_v1/'+n for n in roles}
assert len(current) == 667 and set(current)-set(before) == added
assert changed == {'modules/drive_catalog/catalog.c', 'modules/drive_catalog/catalog.h',
                   'experiments/catalog_drive_v1/models.c', 'experiments/catalog_drive_v1/contract.c',
                   'experiments/catalog_drive_v1/ui_checks.c'}
assert all(sha(repo/n) == h for n, h in voices.items())
provenance = load(e/'asset_provenance.json')
parent = a.workspace/'baselines/F3_local_atlas_v1'
assert sha(parent/'manifest.json') == provenance['parent_manifest_sha256']
manifest = {v['path']: v['sha256'] for v in load(parent/'manifest.json')['files']}
for row in provenance['profiles']:
    assert sha(repo/row['path']) == sha(parent/row['parent_path']) == manifest[row['parent_path']] == row['sha256']
    voices[row['path']] = row['sha256']
assert len(voices) == 82
f2 = ['experiments/modal_idle_v1/F2_fixed_idle.msource',
      'experiments/modal_texture_v1/F2_amplitude.mtexture',
      'experiments/spectral_texture_v1/F2_fine_static.sfir']
assert all(sha(repo/n) == sha(parent/'source'/n) for n in f2)
index = repo/'handoff/C文件索引.csv'
rows = list(csv.reader(index.open(encoding='utf-8-sig', newline='')))
if a.stage == 'index':
    assert len(rows) in (665, 668)
    if len(rows) == 665:
        assert all(row[4] == before[row[0]] for row in rows[1:])
    else:
        assert {row[0] for row in rows[1:]} == set(current)
        assert all(row[4] == current[row[0]] for row in rows[1:] if row[0] not in changed)
    for row in rows[1:]:
        row[4] = current[row[0]]
    if len(rows) == 665:
        for n in sorted(added):
            rows.append([n, 'F3局部声纹统一驾驶接入', 'catalog_drive_v1', roles[Path(n).name], current[n]])
    stream = io.StringIO(newline='')
    csv.writer(stream, lineterminator='\n').writerows(rows)
    index.write_text(stream.getvalue(), encoding='utf-8', newline='\n')
    save(e/'C_files_sha256.json', current)
    save(e/'voice_files_sha256.json', voices)
    print('PASS667 C/H:659prior exact5nonDSPchanges3added;76old+6frozen voices/F2 exact')
    raise SystemExit
assert len(rows) == 668 and all(row[4] == current[row[0]] for row in rows[1:])
failed = load(e/'full1/report.json')
assert failed['result'] == 'failed' and b'C4013' in (e/'full1/command_01.log').read_bytes()
for n, h in failed['sources'].items():
    assert sha(e/'full1/exact_sources'/n) == h
for phase in ('full2', 'host2'):
    report = load(e/phase/'report.json')
    assert report['result'] == 'passed'
    for n, h in report['sources'].items():
        assert h == sha(e/phase/'exact_sources'/n), (phase, n)
        # CTest executables/shared kernels unchanged; only the native UI-check
        # harness moved the first settling observation and added probe logging.
        if phase != 'full2' or n != 'experiments/catalog_drive_v1/ui_checks.c':
            assert sha(repo/n) == h, (phase, n)
failed_host = load(e/'host1/report.json')
assert failed_host['result'] == 'failed' and load(e/'host1/ui.json')['failed_line'] == 137
for n, h in failed_host['sources'].items():
    assert sha(e/'host1/exact_sources'/n) == h
tests = ET.parse(e/'full2/ctest.xml').getroot().findall('.//testcase')
assert len(tests) == 68 and all(t.find('failure') is None and t.find('error') is None and t.find('skipped') is None for t in tests)
ui = load(e/'host2/ui.json')
assert ui['result'] == 'pass' and ui['voices'] == len(ui['records']) == 12 and ui['cross_voice_replay_and_live_restore']
probe_max_error = 0
for group in range(2):
    with (e/('host2/ui.json.local%d.probes.csv' % group)).open(newline='', encoding='utf-8') as stream:
        probes = list(csv.DictReader(stream))
    assert [int(row['anchor']) for row in probes] == [0, 2, 1]
    for row in probes:
        probe_max_error = max(probe_max_error, abs(float(row['root_hz'])-float(row['expected_root_hz'])))
assert probe_max_error < .04
reg = load(e/'regress1/report.json')
assert reg['result'] == 'passed' and len(reg['original']) == 10 and len(reg['current']) == 12 and len(reg['native']) == 3
assert reg['both_players_same_identity'] and reg['no_external_voice_paths']
assert reg['render_id'] == load(a.workspace/'baselines/bandlimited_dna_v1/validation.json')['new_render_id']
images = load(e/'review1/report.json')
assert images['result'] == 'nine_native_images_ready' and len(images['images']) == 9
assert load(e/'review1/visual_review.json')['nine_own_window_images_viewed']
for filename, executed in [('tools/prepare_catalog_local_F3_v1.py', 'executed_prepare.py'),
                           ('tools/regress_catalog_local_F3_v1.py', 'regress1/executed_regression.py'),
                           ('tools/review_catalog_local_F3_v1.py', 'review1/executed_review.py')]:
    assert sha(repo/filename) == sha(e/executed)
binary = e/'bin'
binary.mkdir(exist_ok=False)
for n in ('VslAtlasMonitor', 'VslAtlasTake_render', 'catalog_contract_checks',
          'catalog_render_checks', 'catalog_F3_local_checks'):
    shutil.copy2(repo/('build-catalog-local-v1/bin/Release/'+n+'.exe'), binary/(n+'.exe'))
shutil.copy2(__file__, e/'executed_package.py')
sources = [n for n in names if Path(n).suffix in ('.c', '.h', '.cmake', '.in') or n.endswith('CMakeLists.txt')]
sources += list(voices)+f2+['voices/F3_fifth_local_v1/index.json', 'tools/package_catalog_local_F3_v1.py',
    'tools/prepare_catalog_local_F3_v1.py', 'tools/regress_catalog_local_F3_v1.py', 'tools/review_catalog_local_F3_v1.py',
    'tools/build_catalog_drive_v1.py', 'tools/research_archive_v1.py', 'modules/drive_catalog/README.md',
    'research/catalog_local_F3_v1_plan.json', 'research/F3局部声纹接入统一驾驶V1.md',
    'Build-Voice-Catalog.ps1', 'Launch-Voice-Catalog.cmd', 'README.md', 'AGENTS.md',
    'handoff/C文件索引.csv', 'handoff/C模块与接口.md', 'handoff/开发留痕.md', 'handoff/研究续接.md', 'handoff/当前代码阅读入口.md']
validation = dict(result='two_optional_local_F3_banks_in_original_native_driver_and_owned_takes',
    git_parent=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip(),
    previous_goal_turn='MCPS check confirmed existing inventory without synthesis progress; now frozen completed local atlas and integrated it into native driver.',
    C_H_total=667, C_H_prior_exact=659, C_H_changed=5, C_H_added=3, changed_C_H=sorted(changed),
    original_voices_exact=76, frozen_profiles_copied=6, total_voice_files=82, F2_exact=True,
    DSP_controller_take_owned_spatial_C_changed=False, presets=12, V10_contexts=10, analytic_examples=2,
    source_refit=False, new_real_engines=0, new_timbre_accepted=False, default_changed=False,
    source_seed=48271, align_orders=32, root_mapping='1/120 engineering hypothesis',
    separate_local_roots_Hz=[[v['root_hz'] for v in provenance['profiles'] if v['group']==group] for group in ('first','second')],
    CTests=68, CTest_sources_unchanged_after_pass_except_native_UI_checker=True,
    direct_owned_source_frames_per_bank=240123, bank_count=2,
    parameter_owner_poison_and_release=True, whole_direct_source_clock_contract=True,
    source_six_dry_buses_and_driver_state_2_12_exact=True, native_UI=ui,
    native_dynamic_bank_record_frames=240123, native_dynamic_banks=2,
    native_local_probe_max_error_Hz=probe_max_error,
    old_ten_WAV_and_source_exact=True, new_twelve_self_contained_replays=True,
    both_old_and_new_players_accept_all_same_identity=True, render_id=reg['render_id'], take_schema=10, take_controls=32,
    native_images_viewed=9, manual_mouse=False, hearing=False, new_HF_LF_or_room=False,
    state_RPM_load_calibrated=False, high_root_owned_support=False, physical_7_1_4=False, ADI_target_port=False,
    failures_preserved=['full1 C4013 lround:missing math.h;full2 adds header only',
                       'host1 first local probe at1.25s before bench settling;host2 moves to2s, same0.04Hz gate and240123frames; adds actual probe CSV'],
    pending_hearings='F2 and F3 independently pending;no repeated questions or blind strength changes',
    E_feedback='左右关系有改善，音色仍明显电子', downloaded=False, pushed=False, full_goal='active',
    next='Use source-supported independent wider-root/state observations and separate stereo/nonharmonic detail; integrate through same driver. More real engine families and physical7.1.4 remain incomplete.')
inputs = {'before_C_files_sha256.json': e/'before_C_files_sha256.json', 'C_files_sha256.json': e/'C_files_sha256.json',
          'before_voice_files_sha256.json': e/'before_voice_files_sha256.json', 'voice_files_sha256.json': e/'voice_files_sha256.json',
          'local_atlas_manifest.json': parent/'manifest.json',
          'previous_live_manifest.json': a.workspace/'baselines/bandlimited_dna_v1/manifest.json',
          'data_AGENTS.md': a.workspace/'AGENTS.md'}
result = freeze(root, repo, sources, e, inputs, validation)
verify(root)
save(repo/'research/catalog_local_F3_v1_summary.json', dict(validation, **result))
append_index(repo/'handoff/阶段索引.csv', ['catalog_local_F3_v1', 'baselines/catalog_local_F3_v1/manifest.json', result['file_count'], result['manifest_sha256'],
    '12catalog;68CTest;2x240123directsource;10oldWAV exact;two compatible players;native12record-replay and two local sweeps',
    '667C-H659exact5nonDSP3new;82voices;F2 exact;local only/no extraHF-LF/new engines/physical7.1.4;full1fail kept',
    'research/F3局部声纹接入统一驾驶V1.md | research/catalog_local_F3_v1_summary.json', 'baselines/catalog_local_F3_v1/validation.json'])
print(result)

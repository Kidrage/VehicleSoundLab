"""Audit V9 state-DNA evidence and preserve a source/binary delivery delta."""
import argparse
from datetime import datetime, timezone
import difflib
import json
from pathlib import Path
import shutil
import subprocess

from startup_response_evidence_v1 import sha, verify
from vehicle_controller.native import Bridge, Engine
from vehicle_controller import dna_bank as dna, take


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--freeze', type=Path, required=True)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    data = Path('E:/VehicleSoundLab')
    work = data/'references/analysis/state_dna_controller_v1'
    base = data/'baselines/event_candidates_v1/delivery1'
    runtime_base = data/'baselines/dna_controller_v1/delivery1'
    assert not args.freeze.exists(), 'Never overwrite a delivery'
    previous = read(runtime_base/'manifest.json')
    result = read(work/'verification3/report.json')
    ui = read(work/'ui3/report.json')
    assert result['result'] == ui['result'] == 'passed'
    assert len(result['default_V8_exact']) == 27
    verify(repo, read(work/'ui3/source_binding.json'))
    binding = read(work/'verification3/source_binding.json')
    changed_after_native = [row['path'] for row in binding['files']
                            if sha(repo/row['path']) != row['sha256']]
    assert changed_after_native == ['tools/vehicle_controller/ui.py'], changed_after_native
    assert sha(repo/binding['bridge_path']) == binding['bridge_sha256']
    ui_name = 'tools/vehicle_controller/ui.py'
    ui_patch = ''.join(difflib.unified_diff(
        (work/'verification3/exact_sources'/ui_name).read_text(encoding='utf-8').splitlines(True),
        (repo/ui_name).read_text(encoding='utf-8').splitlines(True),
        fromfile='verification3/'+ui_name, tofile='ui3/'+ui_name))
    assert ui['underflows'] == 0 and ui['own_window_closed'] and ui['catalog_restore']
    assert ui['full_32s_cycle'] and ui['saved_take_UI_32s_replay']
    assert ui['state_telemetry_observed'] == [0, 1, 2, 3]
    assert ui['recorded_notices_state_exact'] and ui['final_state']['lifecycle'] == 0
    saved = list((work/'ui3/takes').glob('*.vsltake.json'))
    assert len(saved) == 1
    value = read(saved[0])
    assert value['schema'] == 'vsl.source-controller-take/8'
    assert value['dna_bank'] == read(work/'ui3/editor.dnabank.json')
    for kind in (1, 2):
        assert any(n['type'] == kind and n['action'] == 1 for n in value['source_events'])

    log1, log2 = work/'build1.log', work/'state-check2.log'
    original = log1.read_text(encoding='utf-8-sig')
    assert original.count('...   Passed') == 5
    assert '83% tests passed, 1 tests failed out of 6' in original
    assert '100% tests passed out of 1' in log2.read_text(encoding='utf-8-sig')
    old = {row['path'][5:]: row for row in previous['files'] if row['path'].startswith('repo/')}
    voices, changes = [], []
    for path in sorted((repo/'voices').rglob('*')):
        if path.is_file():
            name = path.relative_to(repo).as_posix()
            assert name in old and sha(path) == old[name]['sha256'], name
            voices.append(dict(path=name, sha256=sha(path)))
    assert len(voices) == 89
    for folder in ('src', 'modules', 'experiments/vehicle_source_v1'):
        for path in (repo/folder).rglob('*'):
            if path.is_file() and path.suffix in ('.c', '.h'):
                name = path.relative_to(repo).as_posix()
                if name not in old or sha(path) != old[name]['sha256']:
                    changes.append(name)
    expected = {
        'experiments/vehicle_source_v1/bridge.c', 'experiments/vehicle_source_v1/bridge.h',
        'experiments/vehicle_source_v1/state_dna_checks.c',
        'modules/atlas_drive/render.c', 'modules/atlas_drive/source_process.h',
        'modules/state_dna/api.h', 'modules/state_dna/bank.c', 'modules/state_dna/lookup.c',
        'modules/state_dna/lookup.h', 'modules/state_dna/voice.c',
        'modules/vehicle_source/assets.c', 'modules/vehicle_source/driver.c',
        'modules/vehicle_source/internal.h', 'modules/vehicle_source/source.c',
        'modules/vehicle_source/state_assets.h', 'modules/vehicle_source/state_dna.c'}
    assert set(changes) == expected, changes
    binaries = {name: repo/path for name, path in (
        ('source-v9', 'build-vehicle-source-v9/bin/Release/vsl_source_bridge.dll'),
        ('source-v8', 'build-vehicle-source-v8/bin/Release/vsl_source_bridge.dll'),
        ('source-v7', 'build-vehicle-source-v7/bin/Release/vsl_source_bridge.dll'),
        ('author-v2', 'build-event-synth-v2/bin/Release/vsl_event_author_bridge.dll'))}
    assert sha(binaries['source-v9']) == result['bridge_sha256']
    assert sha(binaries['source-v8']) == result['old_bridge_sha256']
    for name in ('source-v8', 'source-v7', 'author-v2'):
        key = 'binaries/'+name+'/'+binaries[name].name
        row = next(x for x in previous['files'] if x['path'] == key)
        assert sha(binaries[name]) == row['sha256'], key

    bridge = Bridge(repo)
    assert bridge.abi() == 9 and bridge.event_available_mask == 6
    observed = []
    native = bridge.open_state_dna

    def observe(selection, paths, counts, ratio, seed, align, seconds):
        observed.extend(Path(paths[i].decode('utf-8')) for i in range(sum(counts[i] for i in range(4))))
        assert all(path.is_file() for path in observed)
        return native(selection, paths, counts, ratio, seed, align, seconds)

    bridge.open_state_dna = observe
    bank = dna.validate(read(work/'ui3/editor.dnabank.json'))
    with Engine(bridge, 0, dna_bank=bank) as engine:
        assert observed and all(not path.exists() for path in observed)
        engine.set(dict(engine.controls, mode=0, rpm=3000., ignition=1, start_id=1))
        assert any(any(engine.process(480)) for _ in range(200))
    subprocess.run(['git', 'diff', '--check'], cwd=repo, check=True)
    summary = dict(
        schema='vsl.state-dna-controller-milestone/1', result='passed', verification=result, ui=ui,
        required_CTests=dict(total_distinct_passed=6,
            original_five=dict(log=str(log1), sha256=sha(log1)),
            corrected_new_state_check=dict(log=str(log2), sha256=sha(log2))),
        native_to_final_ui_changes=changed_after_native, final_ui_source_binding=str(work/'ui3/source_binding.json'),
        temp_model_files_removed_before_audio=True, source_C_H_changes=sorted(changes),
        runtime_comparison_base=str(runtime_base), runtime_base_manifest_sha256=sha(runtime_base/'manifest.json'),
        voices_unchanged=voices, binaries={name: dict(path=str(path), sha256=sha(path)) for name, path in binaries.items()},
        base_freeze=str(base), base_manifest_sha256=sha(base/'manifest.json'), freeze=str(args.freeze),
        generator_only=True, spatial_rendering_budget_external=True, ADI_measured=False,
        design_budget=dict(work_MCPS=395, reserve_MCPS=50, planning_MCPS=445, ceiling_MCPS=500),
        persistent_app_restarted=False, owned_test_windows_closed=True, new_download=False,
        commit_or_push=False, goal_complete=False, new_timbre_accepted=False,
        unresolved=['startup hearing', 'confirmed full-band afterfire', 'other independent event timbres',
                    'full RPM/load/state sound quality', 'V9 target-DSP resource qualification'],
        retained_failures=['build1 unsigned-negative expected test formula',
            'verification1 cancelled unsafe native-pointer fixture',
            'verification2 inappropriate fallback PCM assertion across idle startup tail',
            'ui1 restore whitelist missing preset schema7'])
    take.save(repo/'research/state_dna_controller_v1_verification.json', summary)
    args.freeze.mkdir(parents=True, exist_ok=False)
    selected = ['src', 'modules', 'voices', 'experiments/vehicle_source_v1',
        'tools/vehicle_controller', 'tools/vehicle_scenarios', 'tools/sound_designer',
        'tools/run_vehicle_controller.py', 'tools/verify_state_dna_controller_v1.py',
        'tools/verify_state_dna_controller_ui_v1.py', 'tools/finalize_state_dna_controller_v1.py',
        'tools/startup_response_evidence_v1.py', 'Build-Vehicle-Source.ps1', 'Launch-Vehicle-Controller.cmd',
        'handoff/多状态DNA与控制台V9.md', 'handoff/声源生成边界与算力V2.md',
        'handoff/当前代码阅读入口.md', 'research/state_dna_controller_v1_verification.json', 'AGENTS.md']
    for name in selected:
        source, target = repo/name, args.freeze/'repo'/name
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, target, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        else:
            shutil.copy2(source, target)
    shutil.copytree(work, args.freeze/'evidence', ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    (args.freeze/'evidence/native-to-final-ui.patch').write_text(ui_patch, encoding='utf-8')
    for name, path in binaries.items():
        target = args.freeze/'binaries'/name/path.name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    (args.freeze/'README.md').write_text(
        '# 多状态 DNA / 控制台 V9 冻结增量\n\n'
        '基础为event_candidates_v1/delivery1，按manifest的基础链恢复后覆盖repo。'
        'V9 DLL放入repo/build-vehicle-source-v9/bin/Release。此目录不是脱离基础的完整构建包。\n\n'
        '正式证据verification3、ui3；ui3为自有静音窗口32秒流程及32秒保存行程回放，窗口已关闭。'
        '原五项C检查在build1通过，新增状态检查修正夹具后在state-check2通过，共六项不同检查。'
        '失败尝试全部保留。verification3后只有UI排版改变，补丁单独保存，ui3绑定最终源代码。\n\n'
        '保留89声源和原V8/V7/作者二进制。四状态示例是人工编辑，不能当作实车标定或听感认可。'
        '输出16类23个原生干声通道，渲染由外部仓库承担。395+50=445 MCPS仅为设计额度，'
        '没有V9目标板性能证明。启动/真实全频回火/其他事件/全转速负载音色尚未完成。'
        '旧常驻服务没有重启，没有新下载或推送，完整目标继续。\n', encoding='utf-8')
    subprocess.run(['git', 'diff', '--binary', '--output='+str(args.freeze/'working-tree.patch')], cwd=repo, check=True)
    files = [dict(path=path.relative_to(args.freeze).as_posix(), bytes=path.stat().st_size, sha256=sha(path))
             for path in sorted(args.freeze.rglob('*')) if path.is_file()]
    take.save(args.freeze/'manifest.json', dict(schema='vsl.state-dna-controller-delta-freeze/1',
        created=datetime.now(timezone.utc).isoformat(), base_freeze=str(base),
        base_manifest_sha256=sha(base/'manifest.json'), goal_complete=False, files=files))
    print(json.dumps(dict(result='frozen', files=len(files), bytes=sum(row['bytes'] for row in files),
                          path=str(args.freeze)), ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()

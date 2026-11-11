"""Freeze the new native monitor without altering previous baselines/releases."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as file:
        for block in iter(lambda: file.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, required=True)
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    repository = Path(__file__).resolve().parents[1]
    if subprocess.check_output(['git', 'status', '--porcelain'], cwd=repository).strip():
        raise RuntimeError('Commit the tested source before freezing')
    evidence = workspace / 'references/analysis/scene_monitor_v1'
    report = json.loads((evidence / 'report.json').read_text(encoding='utf-8'))
    for relative, expected in report['source_sha256'].items():
        assert sha(repository / relative) == expected, relative
    for relative, expected in report['binary_sha256'].items():
        assert sha(repository / 'handoff-build/bin/Release' / relative) == expected, relative
    tests = repository / 'handoff-build/Testing/Temporary/LastTest.log'
    assert tests.read_bytes().count(b'Test Passed.') == 27
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repository, text=True).strip()
    destination = workspace / 'baselines/scene_monitor_v1'
    destination.mkdir(exist_ok=False)
    shutil.copytree(evidence, destination / 'evidence')
    (destination / 'bin').mkdir()
    for name in report['binary_sha256']:
        if name != 'VslSystem.exe':
            shutil.copy2(repository / 'handoff-build/bin/Release' / name, destination / 'bin' / name)
    shutil.copytree(repository / 'voices/dna_bank_v1', destination / 'voices/dna_bank_v1')
    shutil.copytree(repository / 'voices/coherent_low_v1', destination / 'voices/coherent_low_v1')
    shutil.copy2(tests, destination / 'ctest-27.log')
    subprocess.run(['git', 'archive', '--format=zip', '--output=' + str(destination / 'source.zip'), revision], cwd=repository, check=True)
    (destination / 'Start-Monitor.cmd').write_bytes(b'@echo off\r\ncd /d "%~dp0"\r\nstart "" "bin\\VslSceneMonitor.exe"\r\n')
    (destination / 'README.txt').write_text(
        'DNA／相干低频联合原生监听V1\n源码提交：' + revision + '\n'
        '运行Start-Monitor.cmd，默认停止，按播放开始。\n'
        '默认已认可的V10直送组合；空间监听可选，仍待主观听评。\n'
        'Warm／Hollow为合成测试音，不代表新增实车拟合。\n'
        'evidence/verified_device和verified_ui为最终技术证据，包含控制采用帧和截图。\n'
        '初始隐藏窗口黑图保留为中间记录，不作为最终视觉验证。\n'
        '本轮设备测试提交静音，捕获提交前输出；未宣称人工交互或声音验收。\n'
        'source.zip含本提交源码、模型和文档；Windows重建需要MSVC2022／CMake。\n'
        '尚未完成新DNA宽RPM／负载驾驶接入。旧冻结版本与Release保持原样。\n', encoding='utf-8')
    files = [dict(path=str(p.relative_to(destination)).replace('\\', '/'), bytes=p.stat().st_size, sha256=sha(p))
             for p in destination.rglob('*') if p.is_file()]
    manifest = dict(schema='vsl.scene-monitor-freeze/1', source_revision=revision, files=files,
                    status='Device/control engineering verified; human listening and full driving integration pending')
    path = destination / 'manifest.json'
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    for entry in json.loads(path.read_text(encoding='utf-8'))['files']:
        assert sha(destination / entry['path']) == entry['sha256']
    print(json.dumps(dict(destination=str(destination), source_revision=revision,
                         verified_files=len(files), bytes=sum(e['bytes'] for e in files))))


if __name__ == '__main__':
    main()

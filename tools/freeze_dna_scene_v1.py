"""Freeze a reviewed source revision and its local C-rendered evidence."""
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
    repository = Path(__file__).resolve().parents[1]
    workspace = args.workspace.resolve()
    if subprocess.check_output(['git', 'status', '--porcelain'], cwd=repository).strip():
        raise RuntimeError('Commit the exact source first; freeze requires a clean checkout')
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repository, text=True).strip()
    experiment = workspace / 'references/analysis/dna_scene_v1'
    report = json.loads((experiment / 'report.json').read_text(encoding='utf-8'))
    for relative, expected in report['source_sha256'].items():
        if sha(repository / relative) != expected:
            raise RuntimeError('Source changed after rendering: ' + relative)
    build = repository / 'build-dna-scene-v1'
    probe = build / 'Release/dna_scene_probe.exe'
    assert sha(probe) == report['probe_sha256']
    qa = json.loads((experiment / 'browser_qa.json').read_text())
    assert qa['status'] == 'pass' and qa['loaded_players'] == 8 and qa['muted']
    tests = repository / 'handoff-build/Testing/Temporary/LastTest.log'
    assert tests.read_text(encoding='utf-8').count('Test Passed.') == 26
    destination = workspace / 'baselines/dna_scene_v1'
    destination.mkdir(exist_ok=False)
    shutil.copytree(experiment, destination / 'evidence')
    (destination / 'bin').mkdir()
    shutil.copy2(probe, destination / 'bin' / probe.name)
    shutil.copy2(build / 'Release/dna_scene_checks.exe', destination / 'bin/dna_scene_checks.exe')
    shutil.copy2(tests, destination / 'ctest-26.log')
    shutil.copy2(build / 'Testing/Temporary/LastTest.log', destination / 'ctest-adapter.log')
    page = (workspace / 'research/DNA空间接入V1.html').read_text(encoding='utf-8')
    prefix = '../references/analysis/dna_scene_v1/audition/'
    assert page.count(prefix) == 8
    (destination / 'review.html').write_text(page.replace(prefix, 'evidence/audition/'), encoding='utf-8')
    subprocess.run(['git', 'archive', '--format=zip', '--output=' + str(destination / 'source.zip'), revision], cwd=repository, check=True)
    (destination / 'README.txt').write_text(
        'DNA／相干低频空间接入V1\n源码提交：' + revision + '\n'
        'review.html为便携立体声试听；evidence/raw保留浮点、独立层及十源分轨。\n'
        'source.zip是该提交全部Git源码／模型／文档；依赖MSVC2022与CMake重新构建。\n'
        '源与低频干声逐样本复现，统一26项CTest通过；空间听评待确认。\n'
        '固定V10情境，未完成宽RPM／负载或新DNA驾驶状态接入。\n'
        '原冻结coherent_low_v1和handoff Release保持原样；后续反馈另建记录。\n', encoding='utf-8')
    entries = [dict(path=str(p.relative_to(destination)).replace('\\', '/'), bytes=p.stat().st_size, sha256=sha(p))
               for p in destination.rglob('*') if p.is_file()]
    manifest = dict(schema='vsl.dna-scene-freeze/1', source_revision=revision, files=entries,
                    status='Engineering verified; spatial listening pending; goal incomplete')
    manifest_path = destination / 'manifest.json'
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    for item in json.loads(manifest_path.read_text(encoding='utf-8'))['files']:
        assert sha(destination / item['path']) == item['sha256']
    print(json.dumps(dict(destination=str(destination), source_revision=revision,
                         verified_files=len(entries), bytes=sum(item['bytes'] for item in entries))))


if __name__ == '__main__':
    main()

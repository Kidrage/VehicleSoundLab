"""Freeze all exterior-anchor stages with committed source and final validation."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import zipfile


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace', type=Path, required=True)
args = parser.parse_args()
repository = Path(__file__).resolve().parents[1]
if subprocess.check_output(['git', 'status', '--porcelain'], cwd=repository).strip():
    raise RuntimeError('Commit validated source and documentation first')
revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repository, text=True).strip()
source = args.workspace/'references/analysis/exterior_clock_v1'
record = json.loads((source/'driving/verification.json').read_text(encoding='utf-8'))
build = json.loads((source/'anchors_v2/build.json').read_text(encoding='utf-8'))
review = json.loads((source/'review/review.json').read_text(encoding='utf-8'))
browser = json.loads((source/'review/browser_qa.json').read_text(encoding='utf-8'))
assert record['result'] == browser['result'] == 'pass' and not record['accepted']
assert sha(source/'driving/verification.json') == review['validation_sha256']
assert sha(source/'anchors_v2/build.json') == record['build_sha256'] == review['build_sha256']
assert sha(source/'warp_controls_v2/verification.json') == record['warp_control_sha256']
assert sha(repository/'handoff-build/bin/Release/VslAtlasDrive_probe.exe') == record['probe_sha256']
assert sha(repository/'handoff-build/bin/Release/VslSoundDna_probe.exe') == build['probe_sha256']
for mapping in (record['source_sha256'], build['source_sha256']):
    for name, expected in mapping.items():
        assert sha(repository/name) == expected, name
bank = repository/'voices/exterior_anchors_v1'
assert sha(bank/'index.json') == review['bank_index_sha256']
for row in build['anchors']:
    origin = source/'anchors_v2'/row['name']
    assert sha(origin/'voice.model') == sha(bank/(row['name']+'.model')) == row['model_sha256']
    for render in row['render']:
        assert sha(origin/f"raw_{render['pitch']:.1f}.wav") == render['sha256']
for row in record['runs']:
    command = json.loads((source/'driving'/(row['name']+'_command.json')).read_text(encoding='utf-8'))
    assert command['probe_sha256'] == record['probe_sha256']
    for name, expected in row['files_sha256'].items():
        assert command['files_sha256'][name] == sha(source/'driving'/name) == expected, name
for row in review['records']:
    assert sha(source/row['source']) == row['source_sha256']
    assert sha(source/'review'/row['file']) == row['sha256']
assert sha(review['page']) == review['page_sha256']
assert sha(source/'review/drive_trace.png') == review['figure_sha256']
assert sha(repository/'tools/make_exterior_review_v1.py') == review['builder_sha256']
# Fixed-context listening acceptance is not transferred to the new bank.
for name, expected in {
    'voices/dna_bank_v1/V10 Exterior.model': '6f8992e6674f603334f82bdbc526fd8ac5bbe750606154c5e83c166c077bb1b7',
    'voices/coherent_low_v1/measured_phase.model': '9e456a4198bce540a4ccc60220b9cf86e40dc80eadc8d1c2904dc5248715e895',
}.items():
    assert sha(repository/name) == expected, name
test_log = repository/'handoff-build/Testing/Temporary/LastTest.log'
log = test_log.read_bytes().decode('utf-8', errors='replace')
assert log.count('Test Passed.') == 29 and 'Test Failed.' not in log

destination = args.workspace/'baselines/exterior_anchors_v1'
destination.mkdir(exist_ok=False)
# Include partial and superseded analysis too; the manifest marks final paths.
shutil.copytree(source, destination/'evidence')
shutil.copytree(bank, destination/'voices/exterior_anchors_v1')
(destination/'docs').mkdir()
for name in ('驻车车外四锚点V1.md', 'exterior_anchors_v1_summary.json'):
    shutil.copy2(repository/'research'/name, destination/'docs'/name)
(destination/'bin').mkdir()
for folder, name in [('bin/Release', 'VslAtlasDrive_probe.exe'), ('bin/Release', 'VslSoundDna_probe.exe'),
                     ('Release', 'VslAtlas_checks.exe'), ('Release', 'VslAtlasDrive_checks.exe')]:
    shutil.copy2(repository/'handoff-build'/folder/name, destination/'bin'/name)
shutil.copy2(test_log, destination/'LastTest.log')
subprocess.run(['git', 'archive', '--format=zip', '--output='+str(destination/'source.zip'), revision],
               cwd=repository, check=True)
with zipfile.ZipFile(destination/'source.zip') as archive:
    assert archive.testzip() is None
page = Path(review['page']).read_text(encoding='utf-8')
prefix = '../'+(source/'review').relative_to(args.workspace).as_posix()+'/'
assert page.count(prefix) == len(review['records'])+1
(destination/'review.html').write_text(page.replace(prefix, 'evidence/review/'), encoding='utf-8')
(destination/'README.txt').write_text('驻车车外四锚点V1\n源码提交：'+revision+'\n'
    '打开review.html试听。本包为A驻车尾部四档实验，不替代已认可的移动尾排DNA／相干低频。\n'
    '最终依据为evidence/anchors_v2、driving和warp_controls_v2；anchors、initial、warp_controls保留中间尝试。\n'
    '包含全部本轮源码、模型、程序、原始float分轨、遥测、预处理和29项测试；生成声无录音时间轴。\n'
    '原A音视频与Python依赖沿用既有完整交接包，可按来源哈希核对；未重复放入本轮快照。\n'
    '根频率不等于实测RPM；低转带宽与锚点间隔、状态／负载声纹和实时性能仍有缺口。\n'
    '本轮音色听评待定，原生四档驾驶UI和实际设备验证未完成。\n', encoding='utf-8')
files = [dict(path=p.relative_to(destination).as_posix(), bytes=p.stat().st_size, sha256=sha(p))
         for p in sorted(destination.rglob('*')) if p.is_file()]
manifest = dict(schema='vsl.exterior-anchors-freeze/1', source_commit=revision, accepted=False,
    final_evidence=['evidence/anchors_v2', 'evidence/driving', 'evidence/warp_controls_v2'],
    validation_sha256=sha(source/'driving/verification.json'), original_source=build['source'], files=files)
(destination/'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
for row in files:
    assert sha(destination/row['path']) == row['sha256']
print(json.dumps(dict(path=str(destination), commit=revision, files=len(files),
    bytes=sum(f['bytes'] for f in files)), ensure_ascii=False))

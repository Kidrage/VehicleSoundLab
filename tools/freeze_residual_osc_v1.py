"""Freeze residual code, profiles, audio and checks without altering older baselines."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
from urllib.parse import unquote
from html.parser import HTMLParser
import zipfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace', type=Path, required=True)
args = parser.parse_args()
repo = Path(__file__).resolve().parents[1]


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=repo).strip(), 'Commit final sources first'
summary = repo/'research/residual_osc_v1_summary.json'
record = json.loads(summary.read_text(encoding='utf-8'))
assert record['result'] == 'pass' and not record['human_accepted'] and not record['driving_attached']
evidence = args.workspace/'references/analysis/residual_osc_v1'
assert str(evidence) == record['evidence_root']
for name, expected in record['source_sha256'].items():
    assert sha(repo/name) == expected, name
for name, expected in record['evidence_sha256'].items():
    assert sha(evidence/name) == expected, name
review = record['review']
assert sha(review['page']) == review['page_sha256']
for item in review['records']:
    assert sha(evidence/'review'/item['file']) == item['sha256']
probe = repo/'handoff-build/bin/Release/VslResidual_probe.exe'
assert sha(probe) == record['probe_sha256']
revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip()
destination = args.workspace/'baselines/residual_osc_v1'
destination.mkdir(exist_ok=False)
shutil.copytree(evidence, destination/'evidence')
shutil.copytree(repo/'voices/residual_osc_v1', destination/'profiles')
(destination/'docs').mkdir()
for path in (summary, repo/'research/谐波间残差OSC_V1.md'):
    shutil.copy2(path, destination/'docs'/path.name)
page = destination/'docs'/Path(review['page']).name
portable = Path(review['page']).read_text(encoding='utf-8').replace(
    '../references/analysis/residual_osc_v1/', '../evidence/')
page.write_text(portable, encoding='utf-8')


class Assets(HTMLParser):
    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if key == 'src':
                assert (page.parent/unquote(value)).is_file(), value


Assets().feed(portable)
(destination/'bin').mkdir()
shutil.copy2(probe, destination/'bin')
subprocess.run(['git', 'archive', '--format=zip', '--output='+str(destination/'source.zip'), revision],
               cwd=repo, check=True)
with zipfile.ZipFile(destination/'source.zip') as archive:
    assert archive.testzip() is None
(destination/'README.txt').write_text(
    '谐波间残差OSC V1\n提交：'+revision+'\n'
    '独立512 OSC残差层，A驻车车外／E高转车内分别拟合。\n'
    '31项C回归通过；平均能量补偿有效，音色尚未通过听评。\n'
    '不替换已有驾驶宿主、认可DNA／相干低频或历史快照。\n'
    'docs中的HTML可直接打开本包音频；试听统一0.25增益，非响度匹配。\n'
    'evidence/fitted中的FLOAT源可超过满幅，直接试听用evidence/review。\n'
    'source.zip为完整源码；原始录音／前置锚点证据沿用既有交接包。\n', encoding='utf-8')
files = [dict(path=p.relative_to(destination).as_posix(), bytes=p.stat().st_size, sha256=sha(p))
         for p in sorted(destination.rglob('*')) if p.is_file()]
manifest = dict(schema='vsl.residual-osc-freeze/1', source_commit=revision,
                human_accepted=False, driving_attached=False, files=files)
(destination/'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
for row in files:
    assert sha(destination/row['path']) == row['sha256']
print(json.dumps(dict(path=str(destination), commit=revision, files=len(files),
                      bytes=sum(row['bytes'] for row in files)), ensure_ascii=False))

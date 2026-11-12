"""Summarize or freeze same-context startup DNA, including rejected clock evidence."""
import argparse,csv,hashlib,json,shutil,subprocess,zipfile
from pathlib import Path

def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def read(path):return json.loads(path.read_text(encoding='utf-8'))
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True);p.add_argument('--freeze',action='store_true')
a=p.parse_args();repo=Path(__file__).resolve().parents[1];root=a.workspace/'references/analysis/startup_catch_v1'
summary=repo/'research/startup_catch_v1_summary.json'
docs=['research/启动后车内DNAV1.md','research/startup_catch_v1_summary.json','handoff/算法说明.md',
      'handoff/C模块与接口.md','handoff/研究续接.md','handoff/开发留痕.md','handoff/C文件索引.csv','AGENTS.md',
      'voices/startup_settle_v1/README.md','experiments/startup_scene_v1/README.md']
if a.freeze:
    assert not subprocess.check_output(['git','status','--porcelain'],cwd=repo).strip()
    r=read(summary)
    for name,digest in r['current_source_sha256'].items():assert sha(repo/name)==digest,name
    for name,digest in r['evidence_sha256'].items():assert sha(root/name)==digest,name
    out=a.workspace/'baselines/startup_catch_v1';out.mkdir(exist_ok=False)
    shutil.copytree(root,out/'evidence',ignore=shutil.ignore_patterns('__pycache__'));(out/'docs').mkdir()
    for name in docs:shutil.copy2(repo/name,out/'docs'/Path(name).name)
    revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
    subprocess.run(['git','archive','--format=zip','--output='+str(out/'source.zip'),revision],cwd=repo,check=True)
    with zipfile.ZipFile(out/'source.zip') as archive:assert archive.testzip() is None
    files=[dict(path=x.relative_to(out).as_posix(),bytes=x.stat().st_size,sha256=sha(x)) for x in sorted(out.rglob('*')) if x.is_file()]
    (out/'manifest.json').write_text(json.dumps(dict(schema='vsl.startup-catch-freeze/1',source_commit=revision,
        human_accepted=False,fast_catch_fitted=False,files=files),ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    for row in files:assert sha(out/row['path'])==row['sha256']
    print(json.dumps(dict(path=str(out),files=len(files),bytes=sum(v['bytes'] for v in files),commit=revision)))
else:
    build=read(root/'render1/report.json');slow=read(root/'slow3/report.json');review=read(root/'review1/report.json')
    local=read(root/'local1/report.json')
    assert build['result']=='same_A_cabin_candidate_rendered' and review['result']=='pass'
    assert all(row['passed'] for row in slow['pairs']) and all(not row['passed'] for row in local['pairs'])
    assert len(slow['controls'])==7 and slow['controls'][-1]['rejected']
    for reference in (2,3,5):assert sha(root/f'slow2/ref{reference}.npz')==sha(root/f'slow3/ref{reference}.npz')
    for name,digest in build['source_sha256'].items():assert sha(repo/name)==digest,name
    old_index=a.workspace/'baselines/startup_drive_v1/docs/C文件索引.csv'
    with old_index.open(encoding='utf-8-sig') as stream:old={v['文件']:v for v in csv.DictReader(stream)}
    with (repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig') as stream:now={v['文件']:v for v in csv.DictReader(stream)}
    assert len(old)==455 and len(now)==456 and set(old)<=set(now)
    for name,row in old.items():assert row==now[name],name
    for name,row in now.items():assert sha(repo/name)==row['SHA-256'],name
    accepted=read(repo/'research/startup_drive_v1_summary.json')['accepted_model_sha256']
    for name,digest in accepted.items():assert sha(repo/name)==digest,name
    paths=set(build['source_sha256'])|set(docs)|{'handoff/tools/index_sources.py'}
    paths|={x.relative_to(repo).as_posix() for x in (repo/'tools').glob('*startup*_*v1.py')}
    paths|={x.relative_to(repo).as_posix() for x in (repo/'tools/startup_catch_v1').glob('*.py')}
    paths|={x.relative_to(repo).as_posix() for x in (repo/'voices/startup_settle_v1').iterdir() if x.is_file()}
    paths.discard(summary.relative_to(repo).as_posix())
    r=dict(schema='vsl.startup-catch-summary/1',date='2026-11-12',result='same_A_cabin_candidate',
        C_H_count=456,prior455_C_H_and_ownership_unchanged=True,new_C_H=sorted(set(now)-set(old)),
        model=build['profile'],accepted_model_sha256=accepted,controls=slow['controls'],
        stronger_slow3_controls_same_candidate_npz_bytes=True,
        rejected_local_clock_pairs=local['pairs'],slow_clock_pairs=slow['pairs'],fixed_C=build['fixed'],
        driver_checks=build['driver_checks'],page=review['page'],human_accepted=False,
        fast_catch_fitted=False,default_changed=False,new_device_checked=False,
        limits=['Only local slow settling clock and training context, not physical RPM or fast catch',
                '300..8000Hz deficit2.4..4.55dB remains; no added residual compensation',
                'Original driver timing/root mapping engineering; full startup not restored',
                'No new native host, take schema, UI, long-run or physical12speaker acceptance'],
        current_source_sha256={name:sha(repo/name) for name in sorted(paths)},
        c_index_sha256=sha(repo/'handoff/C文件索引.csv'),
        evidence_sha256={x.relative_to(root).as_posix():sha(x) for x in sorted(root.rglob('*')) if x.is_file() and '__pycache__' not in x.parts})
    summary.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(dict(result=r['result'],C_H=r['C_H_count'],prior455_unchanged=True,clips=len(review['clips']),known_controls=len(slow['controls']))))

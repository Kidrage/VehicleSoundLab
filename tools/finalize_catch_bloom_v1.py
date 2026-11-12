"""Audit/freeze CATCH LF evidence without promoting training power to acceptance."""
import argparse,csv,hashlib,json,shutil,subprocess,zipfile
from pathlib import Path
def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True);p.add_argument('--freeze',action='store_true')
a=p.parse_args();repo=Path(__file__).resolve().parents[1];root=a.workspace/'references/analysis/catch_bloom_v1'
fast=a.workspace/'references/analysis/startup_flare_v1/exploration1';summary=repo/'research/catch_bloom_v1_summary.json'
def read(path):return json.loads(path.read_text(encoding='utf-8'))
docs=['research/接火低频建立V1.md','research/catch_bloom_v1_summary.json','handoff/C文件索引.csv',
      'handoff/C模块与接口.md','handoff/算法说明.md','handoff/研究续接.md','handoff/开发留痕.md','AGENTS.md',
      'README.md','modules/catch_bloom/README.md','experiments/catch_bloom_v1/README.md','voices/catch_bloom_v1/README.md']
if a.freeze:
    assert not subprocess.check_output(['git','status','--porcelain'],cwd=repo).strip()
    r=read(summary)
    for name,digest in r['current_source_sha256'].items():assert sha(repo/name)==digest,name
    for name,digest in r['evidence_sha256'].items():assert sha(root/name)==digest,name
    for name,digest in r['fast_clock_evidence_sha256'].items():assert sha(fast/name)==digest,name
    out=a.workspace/'baselines/catch_bloom_v1';out.mkdir(exist_ok=False)
    shutil.copytree(root,out/'evidence',ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copytree(fast,out/'fast_clock_failures',ignore=shutil.ignore_patterns('__pycache__'))
    (out/'docs').mkdir()
    for name in docs:shutil.copy2(repo/name,out/'docs'/Path(name).name)
    revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
    subprocess.run(['git','archive','--format=zip','--output='+str(out/'source.zip'),revision],cwd=repo,check=True)
    with zipfile.ZipFile(out/'source.zip') as archive:assert archive.testzip() is None
    files=[dict(path=x.relative_to(out).as_posix(),bytes=x.stat().st_size,sha256=sha(x)) for x in sorted(out.rglob('*')) if x.is_file()]
    (out/'manifest.json').write_text(json.dumps(dict(schema='vsl.catch-bloom-freeze/1',source_commit=revision,
        human_accepted=False,native_UI_integrated=False,files=files),ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    for row in files:assert sha(out/row['path'])==row['sha256']
    print(json.dumps(dict(path=str(out),files=len(files),bytes=sum(x['bytes'] for x in files),commit=revision)))
else:
    build=read(root/'build2/report.json');fit=read(root/'fit2/report.json');render=read(root/'render1/report.json')
    review=read(root/'review1/report.json');trace=read(root/'v6_trace2/report.json');clock=read(fast/'report.json')
    assert build['result']=='isolated_adapter_built_and_checked' and fit['result']=='coarse_support_candidate_fitted'
    assert render['result']=='C_candidate_render_and_isolation_pass' and review['result']=='pass' and trace['result']=='literal_paths_checked'
    assert len(clock['cases'])==93 and not any(v.get('rows') for v in clock['cases'])
    with (a.workspace/'baselines/startup_catch_v1/docs/C文件索引.csv').open(encoding='utf-8-sig') as stream:old={v['文件']:v for v in csv.DictReader(stream)}
    with (repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig') as stream:now={v['文件']:v for v in csv.DictReader(stream)}
    assert len(old)==456 and len(now)==466 and set(old)<=set(now)
    for name,row in old.items():assert row==now[name],name
    for name,row in now.items():assert sha(repo/name)==row['SHA-256'],name
    for name,digest in build['source_sha256'].items():assert sha(repo/name)==digest,name
    accepted=read(repo/'research/startup_catch_v1_summary.json')['accepted_model_sha256']
    for name,digest in accepted.items():assert sha(repo/name)==digest,name
    assert sha(repo/'voices/catch_bloom_v1/A cabin catch.cb')==fit['profile']['sha256']
    paths=set(build['source_sha256'])|set(docs)|{'handoff/tools/index_sources.py','tools/explore_startup_flare_v1.py'}
    paths|={x.relative_to(repo).as_posix() for x in (repo/'tools').glob('*catch_bloom_v1.py')}
    paths|={x.relative_to(repo).as_posix() for x in (repo/'tools/catch_bloom_v1').glob('*.py')}
    paths|={x.relative_to(repo).as_posix() for x in (repo/'voices/catch_bloom_v1').iterdir() if x.is_file()}
    paths.discard(summary.relative_to(repo).as_posix())
    r=dict(schema='vsl.catch-bloom-summary/1',date='2026-11-12',result='isolated_coherent_catch_support_candidate',
        C_H_count=466,prior456_C_H_and_ownership_unchanged=True,new_C_H=sorted(set(now)-set(old)),
        profile=fit['profile'],power_target_dB=fit['fit_target_catch_to_settle_dB'],power_candidate_dB=fit['candidate_catch_to_settle_dB'],
        power_fit_residual_dB=fit['fit_residual_dB'],temporal_amplitude_RMSE=fit['temporal_amplitude_RMSE'],
        known_power_error=fit['known_band_power_max_error'],known_beta_error=fit['known_beta_max_error'],
        new_C_contract_pass=True,old43_CTests_not_repeated=True,old_four_stems_and_zero_mix_byte_equal=True,
        render_cases=render['cases'],two_starts_band_observations=render['two_starts_band_observations'],
        page=review['page'],V6=trace,fast_clock_cases=93,fast_clock_connected=0,
        accepted_model_sha256=accepted,human_accepted=False,default_changed=False,native_UI_integrated=False,
        schema4_changed=False,new_device_checked=False,
        limits=fit['limits']+['Fast catch pitch and300Hz+ DNA deficits remain','No complete state/diverse engines/long-run/physical12speaker acceptance'],
        current_source_sha256={name:sha(repo/name) for name in sorted(paths)},
        evidence_sha256={x.relative_to(root).as_posix():sha(x) for x in sorted(root.rglob('*')) if x.is_file() and '__pycache__' not in x.parts},
        fast_clock_evidence_sha256={x.relative_to(fast).as_posix():sha(x) for x in sorted(fast.rglob('*')) if x.is_file() and '__pycache__' not in x.parts})
    summary.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(dict(result=r['result'],C_H=466,old456_unchanged=True,clips=len(review['clips']),fast_clock_connected=0)))

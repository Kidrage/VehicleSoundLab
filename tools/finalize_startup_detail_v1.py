"""Bind same-A detail evidence and unchanged runtime sources; publish/freeze candidate."""
import argparse,csv,hashlib,json,re,shutil,subprocess,zipfile
from pathlib import Path


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def read(path):return json.loads(path.read_text(encoding='utf-8'))


def hashes(root):
    return {x.relative_to(root).as_posix():sha(x) for x in sorted(root.rglob('*'))
            if x.is_file() and '__pycache__' not in x.parts}


def index(path):
    with path.open(encoding='utf-8-sig') as stream:
        rows=list(csv.DictReader(stream))
    result={v['文件']:v for v in rows};assert len(result)==len(rows);return result


p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True);p.add_argument('--freeze',action='store_true')
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
root=a.workspace/'references/analysis/startup_detail_v1';summary=repo/'research/startup_detail_v1_summary.json'
docs=['research/启动车内细节V1.md','research/startup_detail_v1_summary.json','README.md','AGENTS.md',
      'handoff/算法说明.md','handoff/C模块与接口.md','handoff/研究续接.md','handoff/开发留痕.md','handoff/C文件索引.csv',
      'voices/startup_detail_v1/README.md','voices/startup_detail_v1/index.json','experiments/startup_detail_v1/README.md']

if a.freeze:
    assert not subprocess.check_output(['git','status','--porcelain'],cwd=repo).strip(),'dirty checkout'
    r=read(summary)
    for name,digest in r['current_source_sha256'].items():assert sha(repo/name)==digest,name
    assert hashes(root)==r['evidence_sha256'],'evidence changed'
    out=a.workspace/'baselines/startup_detail_v1';out.mkdir(exist_ok=False)
    shutil.copytree(root,out/'evidence',ignore=shutil.ignore_patterns('__pycache__'))
    for name in docs:
        dest=out/'docs'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,dest)
    revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
    subprocess.run(['git','archive','--format=zip','--output='+str(out/'source.zip'),revision],cwd=repo,check=True)
    with zipfile.ZipFile(out/'source.zip') as archive:assert archive.testzip() is None
    files=[dict(path=x.relative_to(out).as_posix(),bytes=x.stat().st_size,sha256=sha(x))
           for x in sorted(out.rglob('*')) if x.is_file()]
    (out/'manifest.json').write_text(json.dumps(dict(schema='vsl.startup-detail-freeze/1',source_commit=revision,
        human_accepted=False,native_UI_integrated=False,new_device_checked=False,files=files),
        ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    for row in files:assert sha(out/row['path'])==row['sha256'],row['path']
    print(json.dumps(dict(path=str(out),files=len(files),bytes=sum(x['bytes'] for x in files),commit=revision)))
else:
    fit=read(root/'fit1/report.json');render=read(root/'render3/report.json');review=read(root/'review1/report.json')
    assert fit['result']=='same_A_additive_stereo_candidate_fitted' and len(fit['controls'])==7
    assert render['result']=='unified_C_detail_candidate_rendered' and review['result']=='pass'
    assert all(v['passed'] for v in fit['controls'])
    assert len(fit['rows'])==12 and sum(v['accepted'] for v in fit['rows'])==11
    rejected=[v for v in fit['rows'] if not v['accepted']]
    assert len(rejected)==1 and rejected[0]['hz']==[600,850] and rejected[0]['power']==[0,0]
    for name,digest in fit['source_sha256'].items():assert sha(repo/name)==digest,name
    for name,digest in render['source_sha256'].items():assert sha(repo/name)==digest,name
    assert sha(root/'render3/bin/startup_detail_probe.exe')==render['binary_sha256']
    assert not re.search(r'warning\s+[A-Z]\d+', (root/'render3/command_01.log').read_text(encoding='utf-8'))
    old=index(root/'render3/before_C文件索引.csv');now=index(repo/'handoff/C文件索引.csv')
    assert len(old)==468 and len(now)==469 and set(old)<=set(now)
    for name,row in old.items():assert now[name]==row and sha(repo/name)==row['SHA-256'],name
    assert sorted(set(now)-set(old))==['experiments/startup_detail_v1/probe.c']
    assert sha(repo/'experiments/startup_detail_v1/probe.c')==now['experiments/startup_detail_v1/probe.c']['SHA-256']
    # The warning and provenance fixes must not change any generated samples or control CSVs.
    reference=hashes(root/'render1/renders')
    assert len(reference)==96
    for number in (2,3):assert hashes(root/f'render{number}/renders')==reference,number
    assert render['old_scene_six_files_byte_equal']
    assert len(render['integration'])==3 and len(render['hold'])==3
    assert all(v['front_equal'] and v['other10_zero'] for v in render['integration'])
    accepted=read(repo/'research/catch_drive_v1_summary.json')['accepted_model_sha256']
    for name,digest in accepted.items():assert sha(repo/name)==digest,name
    frozen=a.workspace/'baselines/startup_catch_v1';manifest=read(frozen/'manifest.json')
    identities={v['path']:v['sha256'] for v in manifest['files']}
    for name,digest in fit['inputs'].items():assert sha(frozen/name)==identities[name]==digest,name
    dna=frozen/'evidence/render1/A start cabin settle.model'
    assert sha(dna)==identities['evidence/render1/A start cabin settle.model']==fit['DNA_sha256']
    for name,digest in render['model_sha256'].items():assert sha(repo/name)==digest,name
    assert len(review['clips'])==8
    assert sha(a.workspace/'research/启动车内细节V1.html')==review['page_sha256']
    model=root/'fit1'/fit['profile']['file'];assert sha(model)==fit['profile']['sha256']
    voices=repo/'voices/startup_detail_v1';voices.mkdir(exist_ok=True)
    dest=voices/model.name
    if dest.exists():assert sha(dest)==sha(model)
    else:shutil.copy2(model,dest)
    voice_index=dict(schema='vsl.startup-detail-models/1',context='A V10 startup settling cabin',
        source_seconds=[38.48,39.51],DNA_sha256=fit['DNA_sha256'],file=model.name,model_sha256=sha(model),
        fit_report_sha256=sha(root/'fit1/report.json'),active_bands=11,silent_infeasible_band_Hz=[600,850],
        human_accepted=False,native_default=False,limits=fit['limits'])
    (voices/'index.json').write_text(json.dumps(voice_index,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    paths=set(now)|set(fit['source_sha256'])|set(render['source_sha256'])|set(docs)|set(accepted)|{
        'handoff/tools/index_sources.py','tools/review_startup_detail_v1.py','tools/finalize_startup_detail_v1.py'}
    paths|={x.relative_to(repo).as_posix() for x in voices.iterdir() if x.is_file()}
    paths|=set(render['model_sha256']);paths.discard(summary.relative_to(repo).as_posix())
    r=dict(schema='vsl.startup-detail-summary/1',date='2026-11-12',result='same_A_static_detail_offline_candidate',
        C_H_count=469,prior468_C_H_and_ownership_unchanged=True,new_C_H=['experiments/startup_detail_v1/probe.c'],
        model=voice_index,known_controls=fit['controls'],infeasible_band=rejected[0],local_halves=fit['local_halves'],
        integration=render['integration'],hold=render['hold'],old_scene_six_files_byte_equal=True,
        render1_2_3_all_96_audio_CSV_files_byte_equal=True,old45_CTests_not_repeated=True,
        new_device_checked=False,native_UI_integrated=False,take_schema_changed=False,human_accepted=False,
        accepted_model_sha256=accepted,page=review['page'],clips=review['clips'],
        limits=fit['limits']+render['limits']+['No full state/diverse engines/long-run/physical12speaker acceptance'],
        current_source_sha256={name:sha(repo/name) for name in sorted(paths)},evidence_sha256=hashes(root))
    summary.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(dict(result=r['result'],C_H=469,old468_unchanged=True,
        clips=len(review['clips']),evidence_files=len(r['evidence_sha256']))))

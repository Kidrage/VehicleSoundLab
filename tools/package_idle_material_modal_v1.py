"""Freeze idle extraction/prototype, including failures and exact evidence."""
import argparse,csv,hashlib,io,json,shutil,subprocess,zipfile
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--stage',choices=['freeze','verify'],required=True);a=p.parse_args()
repo=Path(__file__).resolve().parents[1]; root=a.workspace/'baselines/idle_material_modal_v1'

def sha(p):
    with p.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def load(p):return json.loads(p.read_text(encoding='utf-8'))
def save(p,obj):p.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

if a.stage=='freeze':
    root.mkdir(parents=True,exist_ok=False)
    analysis=a.workspace/'references/analysis'
    material=load(analysis/'idle_material_v1/observe2/report.json')
    audit=load(analysis/'idle_material_v1/audit1/report.json')
    fit=load(analysis/'idle_modal_v1/trial4/report.json')
    checked=load(analysis/'idle_modal_v1/audit2/report.json')
    review=load(analysis/'idle_modal_v1/review2/report.json')
    assert material['result']=='four_raw_contexts_and_actual_idle_coverage_extracted'
    assert audit['result']=='all30_native_tiles_and2_literal_fullband_DFTs_verified'
    assert fit['result']=='experimental_native_idle_candidate_rendered_not_listening_accepted'
    assert checked['result']=='native_sources_modal_samples_three_seeds_and_AR_scale_independently_checked'
    assert checked['profile_has_no_observation_timeline'] and review['one_player']
    assert all(v['decoded_samples_exact'] for v in fit['profile_evidence_separation_audio_identity'].values())
    assert all(load(analysis/path/'report.json')['result']=='failed' for path in (
        'idle_material_v1/observe1','idle_modal_v1/trial1','idle_modal_v1/trial3'))
    prior=analysis/'qp_path_repair_v1/final1'
    invariants={}
    for name,count in [('C_files_sha256.json',540),('voice_files_sha256.json',67)]:
        values=load(prior/name);assert len(values)==count
        assert all(sha(repo/path)==digest for path,digest in values.items())
        shutil.copy2(prior/name,root/name);invariants[name]=count
    subprocess.run(['git','diff','--exit-code','HEAD','--','src','modules','experiments','voices','CMakeLists.txt'],
        cwd=repo,capture_output=True,check=True)
    # The latest page replaces its provisional pointer in working memory;
    # neither earlier report nor earlier exact sources are edited.
    for path in [repo/'AGENTS.md',a.workspace/'AGENTS.md']:
        data=path.read_bytes();old=b'idle_modal_v1/review1/';new=b'idle_modal_v1/review2/'
        if old in data:path.write_bytes(data.replace(old,new))
    source_paths=[repo/'AGENTS.md',repo/'research/怠速素材与独立声线V1.md',
        repo/'research/idle_material_v1_plan.json',repo/'research/idle_modal_v1_plan.json',
        repo/'handoff/算法说明.md',repo/'handoff/研究续接.md',repo/'handoff/开发留痕.md',
        repo/'tools/analyze_idle_material_v1.py',repo/'tools/audit_idle_material_v1.py',
        repo/'tools/plot_idle_material_v1.py',repo/'tools/run_idle_modal_v1.py',
        repo/'tools/audit_idle_modal_v1.py',repo/'tools/review_idle_modal_v1.py',Path(__file__),
        *sorted((repo/'tools/idle_material_v1').glob('*.py')),
        *sorted((repo/'tools/idle_modal_v1').glob('*.py'))]
    # Include reused Python dependencies from the actual successful runs.
    source_paths+=list(repo/path for path in fit['sources'])
    for path in sorted(set(source_paths)):
        dest=root/'source'/path.relative_to(repo);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,dest)
    shutil.copy2(a.workspace/'AGENTS.md',root/'data_workspace_AGENTS.md')
    for name in ['idle_material_v1','idle_modal_v1']:
        shutil.copytree(analysis/name,root/'evidence'/name)
    binary=repo/'build-state-passage-v1/Release/state_passage_probe.exe'
    assert sha(binary)==review['old_DNA_baseline']['exe_sha256']
    (root/'bin').mkdir();shutil.copy2(binary,root/'bin/state_passage_probe.exe')
    with zipfile.ZipFile(root/'source.zip','w',compression=zipfile.ZIP_DEFLATED) as z:
        for path in sorted((root/'source').rglob('*')):
            if path.is_file():z.write(path,path.relative_to(root/'source').as_posix())
    validation=dict(schema='vsl.idle-material-modal-freeze/1',
        result='native_idle_material_and_independent_modal_prototype_pending_listening',
        source_git_parent=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
        catalogue_sha256=material['catalogue_sha256'],approved_source_inventory=material['inventory'],
        runtime_invariants=invariants,source_RPM=None,shared_phase_qualified=False,runtime_changed=False,
        modal_modes=fit['modes'],resonator_bands=6,train_seconds=[6,9],holdout_seconds=[9,12],
        seed_count=3,checks=checked['checks'],url=review['url'],listening_accepted=False,
        retained_failed_runs=['idle_material_v1/observe1','idle_modal_v1/trial1','idle_modal_v1/trial3'],
        retained_intermediate_runs=['idle_modal_v1/trial2','idle_modal_v1/audit1','idle_modal_v1/review1'],
        limitation='Independent fixed-Hz modes may beat; not common-phase DNA, measured RPM/load, full driving coverage or listening acceptance.')
    save(root/'validation.json',validation)
    entries=[dict(path=path.relative_to(root).as_posix(),bytes=path.stat().st_size,sha256=sha(path))
        for path in sorted(root.rglob('*')) if path.is_file()]
    manifest=dict(schema='vsl.stage-manifest/1',files=entries,file_count=len(entries),bytes=sum(v['bytes'] for v in entries))
    save(root/'manifest.json',manifest);digest=sha(root/'manifest.json')
    summary=dict(validation,freeze='baselines/idle_material_modal_v1',manifest_sha256=digest,
        file_count=manifest['file_count'],bytes=manifest['bytes'])
    save(repo/'research/idle_material_modal_v1_summary.json',summary)
    index=repo/'handoff/阶段索引.csv';before=index.read_bytes()
    row=['idle_material_modal_v1','baselines/idle_material_modal_v1/manifest.json',str(len(entries)),digest,
        'Native4contexts/actualCidle deficit; F2 independent13mode+6resonator fixed-idle prototype. All3seeds and samples/PSD/AR audited; not shared-phase DNA or runtime change. Failures retained',
        'Pending listening; moving35 retained; independent-mode beating remains possible',
        'research/怠速素材与独立声线V1.md | research/idle_material_modal_v1_summary.json',
        'baselines/idle_material_modal_v1/validation.json | references/analysis/idle_modal_v1/review2/report.json']
    buffer=io.StringIO(newline='');csv.writer(buffer,lineterminator='\r\n').writerow(row)
    if b'idle_material_modal_v1,' in before:raise ValueError('Stage already indexed')
    index.write_bytes(before+(b'' if before.endswith(b'\n') else b'\r\n')+buffer.getvalue().encode('utf-8'))
    assert index.read_bytes().startswith(before)
    print(json.dumps(dict(stage='frozen',files=len(entries),bytes=manifest['bytes'],manifest_sha256=digest)),flush=True)
else:
    m=load(root/'manifest.json');assert m['file_count']==len(m['files'])
    for item in m['files']:
        path=root/item['path'];assert path.stat().st_size==item['bytes'] and sha(path)==item['sha256'],item['path']
    for name in ['C_files_sha256.json','voice_files_sha256.json']:
        assert all(sha(repo/path)==digest for path,digest in load(root/name).items())
    summary=load(repo/'research/idle_material_modal_v1_summary.json')
    assert summary['manifest_sha256']==sha(root/'manifest.json')
    with (repo/'handoff/阶段索引.csv').open(encoding='utf-8-sig',newline='') as stream:rows=list(csv.reader(stream))
    assert all(len(row)==8 for row in rows)
    assert rows[-1][0]=='idle_material_modal_v1' and rows[-1][3]==sha(root/'manifest.json')
    print(json.dumps(dict(stage='verified',files=m['file_count'],bytes=m['bytes'])),flush=True)

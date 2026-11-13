"""Index and freeze isolated idle C implementation and both validation runs."""
import argparse,csv,io,json,shutil,subprocess,zipfile
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--stage',choices=['freeze','verify'],required=True);a=p.parse_args();repo=Path(__file__).resolve().parents[1]
import hashlib
def sha(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def load(path):return json.loads(path.read_text(encoding='utf-8'))
def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
root=a.workspace/'baselines/idle_modal_c_v1';analysis=a.workspace/'references/analysis/idle_modal_c_v1'
if a.stage=='freeze':
    first,checked=load(analysis/'verify1/report.json'),load(analysis/'verify2/report.json')
    assert first['result']==checked['result']=='isolated_C_contracts_and_all_frozen_idle_samples_pass'
    assert checked['CTest_count']==2 and len(checked['comparisons'])==11 and checked['maximum_FS_error']<=1e-7
    assert all(sha(repo/path)==sha(analysis/'verify2/exact_sources'/path)==digest for path,digest in checked['sources'].items())
    parent=load(repo/'research/idle_material_modal_v1_summary.json')
    assert sha(a.workspace/parent['freeze']/'manifest.json')==parent['manifest_sha256']
    root.mkdir(parents=True,exist_ok=False)
    # Existing source ownership and hashes remain unchanged; append only the
    # ten new C/H rows, preserving every byte of the old index prefix.
    index=repo/'handoff/C文件索引.csv';before=index.read_bytes()
    rows=list(csv.DictReader(io.StringIO(before.decode('utf-8-sig'))));assert len(rows)==540
    for row in rows:assert sha(repo/row['文件'])==row['SHA-256']
    new_files=sorted([*repo.glob('modules/modal_source/*.c'),*repo.glob('modules/modal_source/*.h'),
        *repo.glob('experiments/modal_idle_v1/*.c'),*repo.glob('experiments/modal_idle_v1/*.h')])
    assert len(new_files)==10
    added=[]
    for path in new_files:
        if 'modules' in path.parts:
            if path.stem=='io':role,target,detail='独立频率声源IO','modal_source_io','非实时限界读取／事务提交'
            elif path.stem=='voice':role,target,detail='独立频率持续声源','modal_source','持续OSC／左右初相／控制平滑／抗混叠'
            else:role,target,detail='独立频率声源参数','modal_source','不可变通用声线模型校验'
        elif path.stem=='models':role,target,detail='固定怠速研究宿主','modal_idle_models','非实时参数组合／拒绝周期细节；不接驾驶'
        elif path.stem=='probe':role,target,detail='固定怠速离线导出','modal_idle_probe','复用独立OSC和原共振核／三分轨'
        else:role,target,detail='独立声源契约','modal_idle_checks','解析相位／控制／长期／静音／IO验证'
        added.append([path.relative_to(repo).as_posix(),role,target,detail,sha(path)])
    buffer=io.StringIO(newline='');csv.writer(buffer,lineterminator='\n').writerows(added)
    index.write_bytes(before+(b'' if before.endswith(b'\n') else b'\n')+buffer.getvalue().encode('utf-8'))
    assert index.read_bytes().startswith(before)
    all_rows=list(csv.DictReader(io.StringIO(index.read_text(encoding='utf-8-sig'))));assert len(all_rows)==550
    c_hashes={row['文件']:row['SHA-256'] for row in all_rows}
    old=a.workspace/parent['freeze']
    voice=load(old/'voice_files_sha256.json');assert len(voice)==67 and all(sha(repo/path)==digest for path,digest in voice.items())
    save(root/'C_files_sha256.json',c_hashes);save(root/'voice_files_sha256.json',voice)
    for path in [repo/'AGENTS.md',a.workspace/'AGENTS.md']:
        original=path.read_bytes();path.write_bytes(original.replace(b'Review idle_modal_v1/review1 pending',b'Review idle_modal_v1/review2 pending'))
    source_files=set(repo/path for path in checked['sources'])
    source_files.update([Path(__file__),repo/'Build-Idle-Modal-Study.ps1',repo/'AGENTS.md',
        repo/'handoff/C文件索引.csv',repo/'handoff/C模块与接口.md',repo/'handoff/算法说明.md',
        repo/'handoff/研究续接.md',repo/'handoff/开发留痕.md',repo/'research/独立怠速声源C移植V1.md',
        repo/'tools/export_idle_modal_c_v1.py'])
    for path in sorted(source_files):
        dest=root/'source'/path.relative_to(repo);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,dest)
    shutil.copy2(a.workspace/'AGENTS.md',root/'data_workspace_AGENTS.md')
    shutil.copytree(analysis,root/'evidence')
    (root/'bin').mkdir()
    binary=repo/'build-modal-idle-v1/Release/modal_idle_probe.exe';assert sha(binary)==checked['binary_sha256']
    for name in ['modal_idle_probe.exe','modal_idle_checks.exe']:
        shutil.copy2(repo/'build-modal-idle-v1/Release'/name,root/'bin'/name)
    shutil.copy2(repo/'build-modal-idle-v1/Testing/Temporary/LastTest.log',root/'LastTest.log')
    # Smoke the new convenience entry once. It builds only the isolated study.
    cmd=['pwsh','-NoProfile','-File',str(repo/'Build-Idle-Modal-Study.ps1')]
    done=subprocess.run(cmd,cwd=repo,capture_output=True,timeout=180)
    (root/'build_entry.log').write_bytes(done.stdout+done.stderr);assert done.returncode==0
    with zipfile.ZipFile(root/'source.zip','w',compression=zipfile.ZIP_DEFLATED) as z:
        for path in sorted((root/'source').rglob('*')):
            if path.is_file():z.write(path,path.relative_to(root/'source').as_posix())
    validation=dict(schema='vsl.idle-modal-c-freeze/1',result='isolated_fixed_idle_C_port_verified_pending_timbre',
        source_parent=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
        parent_manifest_sha256=parent['manifest_sha256'],original_C_H_unchanged=540,new_C_H=10,indexed_C_H=550,
        original_voices_unchanged=67,tests=2,maximum_sample_FS_error=checked['maximum_FS_error'],
        phase_relations=checked['fixed_parameter_phase_relations'],build_entry_command=cmd,build_entry_pass=True,
        verification_reports={name:sha(analysis/name/'report.json') for name in ['export1','verify1','verify2']},
        native_driver_UI_take_spatial_changed=False,shared_engine_clock=False,listening_accepted=False,
        source_review='http://127.0.0.1:8789/references/analysis/idle_modal_v1/review2/index.html',
        limitation='Independent fixed-Hz modes may beat; neither sample parity nor60s numeric phase tests establish engine-synchronous or full-RPM accuracy.')
    save(root/'validation.json',validation)
    entries=[dict(path=path.relative_to(root).as_posix(),bytes=path.stat().st_size,sha256=sha(path))
        for path in sorted(root.rglob('*')) if path.is_file()]
    manifest=dict(files=entries,file_count=len(entries),bytes=sum(v['bytes'] for v in entries));save(root/'manifest.json',manifest)
    digest=sha(root/'manifest.json')
    save(repo/'research/idle_modal_c_v1_summary.json',dict(validation,freeze='baselines/idle_modal_c_v1',
        manifest_sha256=digest,file_count=len(entries),bytes=manifest['bytes']))
    stage=repo/'handoff/阶段索引.csv';prefix=stage.read_bytes();assert b'\nidle_modal_c_v1,' not in prefix
    row=['idle_modal_c_v1','baselines/idle_modal_c_v1/manifest.json',str(len(entries)),digest,
        'Isolated generic independent OSC C port; original540C-H/67voices unchanged;10new.2CTest/60s oracle/all3seed Python parity pass; no driver adoption',
        'Pending original fixed-idle timbre listening; phase drift remains possible',
        'research/独立怠速声源C移植V1.md | research/idle_modal_c_v1_summary.json',
        'baselines/idle_modal_c_v1/validation.json | baselines/idle_modal_c_v1/evidence/verify2/report.json']
    buffer=io.StringIO(newline='');csv.writer(buffer,lineterminator='\n').writerow(row)
    stage.write_bytes(prefix+(b'' if prefix.endswith(b'\n') else b'\n')+buffer.getvalue().encode('utf-8'))
    assert stage.read_bytes().startswith(prefix)
    print(json.dumps(dict(stage='frozen',files=len(entries),bytes=manifest['bytes'],manifest_sha256=digest)),flush=True)
else:
    manifest=load(root/'manifest.json')
    for item in manifest['files']:
        path=root/item['path'];assert path.stat().st_size==item['bytes'] and sha(path)==item['sha256'],item['path']
    for filename in ['C_files_sha256.json','voice_files_sha256.json']:
        assert all(sha(repo/path)==digest for path,digest in load(root/filename).items())
    summary=load(repo/'research/idle_modal_c_v1_summary.json');assert summary['manifest_sha256']==sha(root/'manifest.json')
    rows=list(csv.DictReader(io.StringIO((repo/'handoff/C文件索引.csv').read_text(encoding='utf-8-sig'))))
    assert len(rows)==550 and {row['文件']:row['SHA-256'] for row in rows}==load(root/'C_files_sha256.json')
    rows=list(csv.reader(io.StringIO((repo/'handoff/阶段索引.csv').read_text(encoding='utf-8-sig'))))
    assert all(len(row)==8 for row in rows) and rows[-1][0]=='idle_modal_c_v1' and rows[-1][3]==summary['manifest_sha256']
    print(json.dumps(dict(stage='verified',files=manifest['file_count'],bytes=manifest['bytes'])),flush=True)

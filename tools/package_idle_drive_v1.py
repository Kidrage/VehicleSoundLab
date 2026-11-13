"""Index and freeze the typed fixed-idle driving/recording experiment."""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import zipfile

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True);p.add_argument('--stage',choices=['index','freeze','verify'],required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
root=a.workspace/'baselines/idle_drive_v1';evidence=a.workspace/'references/analysis/idle_drive_v1'


def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def load(path):return json.loads(path.read_text(encoding='utf-8'))


def save(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')


parent_summary=load(repo/'research/idle_state_v1_summary.json');parent=a.workspace/parent_summary['freeze']
assert sha(parent/'manifest.json')==parent_summary['manifest_sha256']
old=load(parent/'C_files_sha256.json');voices=load(parent/'voice_files_sha256.json')
names=subprocess.check_output(['git','ls-files','-z'],cwd=repo).decode('utf-8').split('\0')
names+=subprocess.check_output(['git','ls-files','--others','--exclude-standard','-z'],cwd=repo).decode('utf-8').split('\0')
current={name:sha(repo/name) for name in sorted(set(names)) if name and Path(name).suffix.lower() in ('.c','.h')}
assert len(old)==562 and len(current)==569 and set(old)<=set(current)
changed={name for name in old if old[name]!=current[name]};new=set(current)-set(old)
assert len(changed)==23 and len(new)==7
assert len(voices)==67 and all(sha(repo/name)==digest for name,digest in voices.items())
index=repo/'handoff/C文件索引.csv'


def c_rows():
    rows=list(csv.reader(io.StringIO(index.read_text(encoding='utf-8-sig'))))
    assert all(len(row)==5 for row in rows)
    return {row[0]:row for row in rows[1:]}


if a.stage=='index':
    rows=c_rows();assert len(rows)==562 and all(rows[name][4]==digest for name,digest in old.items())
    lines=index.read_bytes().splitlines(keepends=True)
    for i,line in enumerate(lines[1:],1):
        name=next(csv.reader([line.decode('utf-8-sig')]))[0]
        if name in changed:lines[i]=line.replace(old[name].encode(),current[name].encode())
    buffer=io.StringIO(newline='');writer=csv.writer(buffer,lineterminator='\n')
    for name in sorted(new):
        if name.startswith('modules/'):
            module,target,job='持续声源状态量','modal_layer','外部gate／18ms量跟随／零量持续推进'
        else:
            module,target,job='怠速统一驾驶实验','idle_drive_v1','只读参数装载／独立控制与拥有行程契约／静音设备留痕'
        writer.writerow([name,module,target,job,current[name]])
    prefix=b''.join(lines);assert prefix.endswith(b'\n');index.write_bytes(prefix+buffer.getvalue().encode())
    assert len(c_rows())==569
    print(json.dumps(dict(result='indexed',total=569,unchanged=539,modified=23,added=7)));raise SystemExit


indexed=c_rows()
assert len(indexed)==569 and all(indexed[name][4]==digest for name,digest in current.items())
if a.stage=='freeze':
    reports={name:load(evidence/name/'report.json') for name in ['kernel1','kernel2','full1','runtime1','package1']}
    assert reports['kernel1']['result']=='failed'
    assert reports['package1']['result']=='failed'
    assert reports['kernel2']['result']=='passed' and reports['kernel2']['tests']==2
    build=reports['full1'];runtime=reports['runtime1']
    assert build['result']=='passed' and build['tests']==59 and build['phase']=='all'
    assert runtime['result']=='typed_idle_owned_controls_legacy_audio_and_muted_device_verified'
    assert runtime['build_proof_sha256']==sha(evidence/'full1/report.json')
    assert sum(row['WAV_bytes_exact'] for row in runtime['legacy'])==84
    assert all(row['driver_CSV_exact'] for row in runtime['legacy'])
    for name,digest in build['sources'].items():assert sha(repo/name)==sha(evidence/'full1/exact_sources'/name)==digest,name
    assert runtime['source_sha256']==sha(repo/'tools/audit_idle_drive_v1.py')
    for name,digest in runtime['binaries'].items():assert sha(evidence/'runtime1/bin'/name)==digest
    device=load(evidence/'runtime1/device/device.json')
    assert runtime['device_report_sha256']==sha(evidence/'runtime1/device/device.json')
    assert device['result']=='pass' and device['frames']==384123 and device['record_hash']==device['play_hash']
    f2={name:sha(repo/name) for name in ['experiments/modal_idle_v1/F2_fixed_idle.msource','experiments/modal_idle_v1/F2_fixed_idle.rdetail','experiments/idle_state_v1/study.h']}
    for name,digest in f2.items():assert sha(parent/'source'/name)==digest
    root.mkdir(parents=True,exist_ok=False);shutil.copytree(evidence,root/'evidence')
    paths=set(build['sources'])|set(current)|set(voices)|set(f2)
    paths.update(['tools/package_idle_drive_v1.py','tools/audit_idle_drive_v1.py','research/怠速统一驾驶与录放V1.md',
                  'research/idle_state_v1_summary.json','modules/modal_layer/README.md','modules/atlas_drive/README.md',
                  'modules/atlas_take/README.md','modules/atlas_take_io/README.md','handoff/C文件索引.csv',
                  'handoff/C模块与接口.md','handoff/算法说明.md','handoff/研究续接.md','handoff/开发留痕.md','AGENTS.md'])
    for name in sorted(paths):
        dest=root/'source'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,dest)
    with zipfile.ZipFile(root/'source.zip','w',compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted((root/'source').rglob('*')):
            if path.is_file():archive.write(path,path.relative_to(root/'source').as_posix())
    save(root/'C_files_sha256.json',current);save(root/'voice_files_sha256.json',voices)
    validation=dict(schema='vsl.idle-drive-freeze/1',result='optional_typed_idle_controls_and_owned_take_verified_timbre_pending',
        parent_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
        parent_freeze=parent_summary['freeze'],parent_manifest_sha256=parent_summary['manifest_sha256'],
        C_H=dict(total=569,unchanged=539,modified=sorted(changed),added=sorted(new)),voices_unchanged=67,F2_assets_and_study_unchanged=f2,
        CTest_count=59,legacy_WAV_byte_exact=84,legacy_driver_CSV_byte_exact=3,
        typed_full_amount_previous_C_sample_exact=True,format_schema=9,control_fields=30,device=device,
        failed_first_build_and_package_retained=True,native_UI_compiled=True,native_UI_manual_interaction_or_visual_verified=False,
        default_executable_replaced=False,timbre_accepted=False,source_timbre_refitted=False,
        actual_F2_RPM_or_load_calibrated=False,physical_7_1_4_verified=False,
        pending='Original F2 fixed idle timbre question; new optional UI manual checks; supported RPM/load and same-car acceleration',
        reports={name:sha(evidence/name/'report.json') for name in reports})
    save(root/'validation.json',validation)
    entries=[dict(path=path.relative_to(root).as_posix(),bytes=path.stat().st_size,sha256=sha(path))
             for path in sorted(root.rglob('*')) if path.is_file()]
    manifest=dict(files=entries,file_count=len(entries),bytes=sum(row['bytes'] for row in entries));save(root/'manifest.json',manifest)
    digest=sha(root/'manifest.json')
    save(repo/'research/idle_drive_v1_summary.json',dict(validation,freeze='baselines/idle_drive_v1',manifest_sha256=digest,file_count=len(entries),bytes=manifest['bytes']))
    stage=repo/'handoff/阶段索引.csv';prefix=stage.read_bytes();assert b'\nidle_drive_v1,' not in prefix
    row=['idle_drive_v1','baselines/idle_drive_v1/manifest.json',str(len(entries)),digest,
         'Typed fixed-idle controls and owned schema9/30;59CTest/84oldWAV exact;384123frame muted device replay/cancel; first missing-header build retained',
         'Source timbre unchanged/pending; UI manual checks and actual RPM/load missing;569C-H indexed/67voices unchanged',
         'research/怠速统一驾驶与录放V1.md | research/idle_drive_v1_summary.json',
         'baselines/idle_drive_v1/validation.json | baselines/idle_drive_v1/evidence/full1/report.json | baselines/idle_drive_v1/evidence/runtime1/device/device.json']
    buffer=io.StringIO(newline='');csv.writer(buffer,lineterminator='\n').writerow(row)
    stage.write_bytes(prefix+(b'' if prefix.endswith(b'\n') else b'\n')+buffer.getvalue().encode())
    assert stage.read_bytes().startswith(prefix)
    print(json.dumps(dict(stage='frozen',files=len(entries),bytes=manifest['bytes'],manifest_sha256=digest)))
else:
    manifest=load(root/'manifest.json')
    for row in manifest['files']:
        path=root/row['path'];assert path.stat().st_size==row['bytes'] and sha(path)==row['sha256']
    assert load(root/'C_files_sha256.json')==current and load(root/'voice_files_sha256.json')==voices
    for name,digest in {**current,**voices}.items():assert sha(root/'source'/name)==digest
    assert sha(root/'source/tools/package_idle_drive_v1.py')==sha(Path(__file__))
    summary=load(repo/'research/idle_drive_v1_summary.json');assert sha(root/'manifest.json')==summary['manifest_sha256']
    rows=list(csv.reader(io.StringIO((repo/'handoff/阶段索引.csv').read_text(encoding='utf-8-sig'))))
    assert all(len(row)==8 for row in rows) and rows[-1][0]=='idle_drive_v1' and rows[-1][3]==summary['manifest_sha256']
    print(json.dumps(dict(stage='verified',files=manifest['file_count'],bytes=manifest['bytes'])))

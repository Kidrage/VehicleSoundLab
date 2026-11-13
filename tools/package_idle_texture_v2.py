"""Freeze exact idle texture study, authored sources and unchanged C inventory."""
import argparse,csv,hashlib,io,json,shutil,subprocess,zipfile
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--stage',choices=['freeze','verify'],required=True);a=p.parse_args()
repo=Path(__file__).resolve().parents[1];root=a.workspace/'baselines/idle_texture_v2'
evidence=a.workspace/'references/analysis/idle_texture_v2'

def load(p):return json.loads(p.read_text(encoding='utf-8'))
def save(p,obj):p.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
def sha(p):
    with p.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def invariants():
    previous=a.workspace/'baselines/idle_drive_v1'
    c=load(previous/'C_files_sha256.json');voices=load(previous/'voice_files_sha256.json')
    assert len(c)==569 and len(voices)==67
    assert all(sha(repo/name)==value for name,value in {**c,**voices}.items())
    subprocess.run(['git','diff','--exit-code','HEAD','--','modules','src','experiments','voices','CMakeLists.txt'],
        cwd=repo,check=True,capture_output=True)
    return c,voices

c,voices=invariants()
if a.stage=='freeze':
    reports={name:load(evidence/name/'report.json') for name in ['observe1','trial1','audit1','review1','check1']}
    assert reports['observe1']['result']=='training_upper_structure_observed'
    assert reports['trial1']['result']=='isolated_fine_and_dynamic_idle_candidates_pending_listening'
    assert reports['audit1']['result']=='three_seeds_fir_and_envelope_replay_verified'
    assert reports['review1']['result']=='single_player_shared_gain_comparison_prepared'
    assert reports['check1']['result']=='pass' and reports['check1']['metadata_combinations']==30
    assert reports['trial1']['old_OSC_parameters_exact'] and len(reports['trial1']['seeds'])==6
    # Every executed source snapshot remains the actual source for this run.
    for name in ['observe1','trial1']:
        for relative,digest in reports[name]['exact_sources'].items():
            assert sha(evidence/name/'exact_sources'/relative)==digest
    root.mkdir(parents=True,exist_ok=False);shutil.copytree(evidence,root/'evidence')
    sources=set()
    for name in ['observe1','trial1']:sources.update(reports[name]['exact_sources'])
    sources.update(['tools/audit_idle_texture_v2.py','tools/review_idle_texture_v2.py','tools/check_idle_texture_v2.cjs',
        'tools/package_idle_texture_v2.py','AGENTS.md','handoff/算法说明.md','handoff/C模块与接口.md',
        'handoff/研究续接.md','handoff/开发留痕.md','research/怠速细节提取V2.md'])
    for name in sorted(sources):
        dest=root/'source'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,dest)
    shutil.copy2(a.workspace/'AGENTS.md',root/'data_workspace_AGENTS.md')
    inputs=root/'inputs';inputs.mkdir()
    old=a.workspace/'references/analysis/idle_modal_v1/trial4'
    for name in ['profile.json','report.json','F2_training.wav','F2_holdout.wav','modal_only.wav',
        *[f'mix_{seed}.wav' for seed in [149921,277139,381611]]]:shutil.copy2(old/name,inputs/name)
    shutil.copy2(a.workspace/'references/segments_v1.json',inputs/'segments_v1.json')
    save(root/'C_files_sha256.json',c);save(root/'voice_files_sha256.json',voices)
    with zipfile.ZipFile(root/'source.zip','w',compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted((root/'source').rglob('*')):
            if path.is_file():archive.write(path,path.relative_to(root/'source').as_posix())
    validation=dict(schema='vsl.idle-texture-freeze/2',result='isolated_source_candidates_verified_pending_listening',
        git_parent=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
        source='F2_tailpipe',train_seconds=[6,9],holdout_seconds=[9,12],
        original_OSC_count=13,original_OSC_parameters_exact=True,filter_taps=8192,
        seed_count=3,methods=['fine','dynamic'],same_gain=reports['review1']['common_gain'],
        C_H_unchanged=len(c),runtime_voice_files_unchanged=len(voices),C_tests_repeated=False,
        shared_phase_qualification=False,RPM_load_calibration=False,room=False,recorded_trajectory=False,
        runtime_changed=False,listening_accepted=False,url=reports['review1']['url'],
        report_hashes={name:sha(evidence/name/'report.json') for name in reports},
        pending='Listen to fine spectrum and slow amplitude separately before runtime adoption; fixed-mode beating and actual state/RPM coverage remain unresolved.')
    save(root/'validation.json',validation)
    entries=[dict(path=p.relative_to(root).as_posix(),bytes=p.stat().st_size,sha256=sha(p))
        for p in sorted(root.rglob('*')) if p.is_file()]
    manifest=dict(files=entries,file_count=len(entries),bytes=sum(x['bytes'] for x in entries));save(root/'manifest.json',manifest)
    digest=sha(root/'manifest.json')
    summary=dict(validation,freeze='baselines/idle_texture_v2',manifest_sha256=digest,
        file_count=manifest['file_count'],bytes=manifest['bytes'])
    save(repo/'research/idle_texture_v2_summary.json',summary)
    index=repo/'handoff/阶段索引.csv';before=index.read_bytes();assert b'\nidle_texture_v2,' not in before
    row=['idle_texture_v2','baselines/idle_texture_v2/manifest.json',str(len(entries)),digest,
        'F2 training upper structure and near-mono observation;13OSC preserved; fine spectral resonators and separate fresh amplitude proxy;3seeds audited',
        'Pending listening; Python only;569C-H/67voices unchanged; no shared-phase or actual RPM/load qualification',
        'research/怠速细节提取V2.md | research/idle_texture_v2_summary.json',
        'baselines/idle_texture_v2/validation.json | baselines/idle_texture_v2/evidence/audit1/report.json']
    buffer=io.StringIO(newline='');csv.writer(buffer,lineterminator='\n').writerow(row)
    index.write_bytes(before+(b'' if before.endswith(b'\n') else b'\n')+buffer.getvalue().encode('utf-8'))
    print(json.dumps(dict(result='frozen',files=len(entries),bytes=manifest['bytes'],manifest_sha256=digest)))
else:
    m=load(root/'manifest.json')
    assert len(m['files'])==m['file_count']
    for item in m['files']:
        path=root/item['path'];assert path.stat().st_size==item['bytes'] and sha(path)==item['sha256'],item['path']
    assert load(root/'C_files_sha256.json')==c and load(root/'voice_files_sha256.json')==voices
    s=load(repo/'research/idle_texture_v2_summary.json');assert s['manifest_sha256']==sha(root/'manifest.json')
    rows=list(csv.reader(io.StringIO((repo/'handoff/阶段索引.csv').read_text(encoding='utf-8-sig'))))
    assert all(len(row)==8 for row in rows)
    matches=[row for row in rows if row[0]=='idle_texture_v2'];assert len(matches)==1 and matches[0][3]==s['manifest_sha256']
    print(json.dumps(dict(result='verified',files=m['file_count'],bytes=m['bytes'],C_H_unchanged=len(c),voices_unchanged=len(voices))))

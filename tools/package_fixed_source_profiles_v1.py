"""Archive generic-source identity proof and rejected A portability attempt."""
import argparse,csv,hashlib,io,json,shutil,subprocess,zipfile
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--stage',choices=['freeze','verify'],required=True);a=p.parse_args()
repo=Path(__file__).resolve().parents[1];root=a.workspace/'baselines/fixed_source_profiles_v1'
evidence=a.workspace/'references/analysis/fixed_source_profiles_v1'

def load(p):return json.loads(p.read_text(encoding='utf-8'))
def save(p,obj):p.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

old=a.workspace/'baselines/idle_drive_v1'
c=load(old/'C_files_sha256.json');voices=load(old/'voice_files_sha256.json')
assert len(c)==569 and len(voices)==67
assert all(sha(repo/name)==digest for name,digest in {**c,**voices}.items())
subprocess.run(['git','diff','--exit-code','HEAD','--','src','modules','experiments','voices','CMakeLists.txt'],
    cwd=repo,capture_output=True,check=True)
if a.stage=='freeze':
    fit=load(evidence/'trial1/report.json');audit=load(evidence/'audit1/report.json');plot=load(evidence/'plot1/report.json')
    assert fit['result']=='two_separate_context_profiles_same_autonomous_kernel_pending_listening'
    assert audit['result']=='generic_F2_identity_verified_A_portability_not_qualified'
    assert plot['result']=='saved_reports_plotted_no_new_fit'
    f2=next(x for x in fit['contexts'] if x['id']=='F2_tailpipe')
    failed=next(x for x in audit['contexts'] if x['id']=='A_exterior_low_rev')
    assert len(f2['seeds'])==6 and all(x['frozen_F2_samples_exact'] for x in f2['seeds'])
    assert failed['modes']==4 and failed['lowest_modal_hz']>120
    assert max(failed['low_modal_power_fraction'])<1e-12
    for name,digest in fit['sources'].items():assert sha(evidence/'trial1/exact_sources'/name)==digest==sha(repo/name)
    assert sha(repo/'tools/audit_fixed_source_profiles_v1.py')==sha(evidence/'audit1/executed_audit.py')
    assert sha(repo/'tools/plot_fixed_source_profiles_v1.py')==sha(evidence/'plot1/executed_plot.py')
    root.mkdir(parents=True,exist_ok=False);shutil.copytree(evidence,root/'evidence')
    sources=set(fit['sources'])|set(['tools/audit_fixed_source_profiles_v1.py','tools/plot_fixed_source_profiles_v1.py',
        'tools/package_fixed_source_profiles_v1.py','AGENTS.md','research/固定声源通用化与适用边界V1.md',
        'handoff/算法说明.md','handoff/研究续接.md','handoff/开发留痕.md'])
    for name in sorted(sources):
        dest=root/'source'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,dest)
    shutil.copy2(a.workspace/'AGENTS.md',root/'data_workspace_AGENTS.md')
    (root/'inputs').mkdir();shutil.copy2(a.workspace/'references/segments_v1.json',root/'inputs/segments_v1.json')
    shutil.copy2(a.workspace/'references/analysis/idle_texture_v2/trial1/profile.json',root/'inputs/frozen_F2_profile.json')
    save(root/'C_files_sha256.json',c);save(root/'voice_files_sha256.json',voices)
    with zipfile.ZipFile(root/'source.zip','w',compression=zipfile.ZIP_DEFLATED) as z:
        for pth in sorted((root/'source').rglob('*')):
            if pth.is_file():z.write(pth,pth.relative_to(root/'source').as_posix())
    validation=dict(schema='vsl.fixed-source-profiles-freeze/1',
        result='generic_F2_exact_A_portability_not_qualified',
        git_parent=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
        parent_freeze='baselines/idle_texture_v2',parent_manifest_sha256=sha(a.workspace/'baselines/idle_texture_v2/manifest.json'),
        F2_all6_FLOAT_files_exact=True,A_source_qualified=False,A_failed_outputs_retained=True,
        oracle_scope='10predeclared samples per file; full F2 identity additionally checked. Not full A sample replay.',
        max_selected_sample_error=max(x['selected_sample_error'] for q in audit['contexts'] for x in q['errors']),
        C_H_unchanged=569,voices_unchanged=67,C_tests_repeated=False,runtime_changed=False,
        measured_RPM_load=False,shared_phase_qualified=False,timbre_accepted=False,
        V2_listening='Asked once, pending; no new A listening question.',
        reports={name:sha(evidence/name/'report.json') for name in ['trial1','audit1','plot1']},
        next='Check A low-line variation and identity using known changing/adjacent/missing-line controls; do not raise random LF or relax support.')
    save(root/'validation.json',validation)
    entries=[dict(path=p.relative_to(root).as_posix(),bytes=p.stat().st_size,sha256=sha(p))
        for p in sorted(root.rglob('*')) if p.is_file()]
    m=dict(files=entries,file_count=len(entries),bytes=sum(x['bytes'] for x in entries));save(root/'manifest.json',m)
    digest=sha(root/'manifest.json');summary=dict(validation,freeze='baselines/fixed_source_profiles_v1',
        manifest_sha256=digest,file_count=m['file_count'],bytes=m['bytes'])
    save(repo/'research/fixed_source_profiles_v1_summary.json',summary)
    index=repo/'handoff/阶段索引.csv';before=index.read_bytes();assert b'\nfixed_source_profiles_v1,' not in before
    row=['fixed_source_profiles_v1','baselines/fixed_source_profiles_v1/manifest.json',str(m['file_count']),digest,
        'Source-independent Python compiler/voice; all6F2 FLOAT files exact; two-context10point scalar/FIR/state checks; all A failure outputs retained',
        'A portability NOT qualified:4modes/no LF OSC; F2 listening pending;569C-H/67voices/runtime unchanged',
        'research/固定声源通用化与适用边界V1.md | research/fixed_source_profiles_v1_summary.json',
        'baselines/fixed_source_profiles_v1/validation.json | baselines/fixed_source_profiles_v1/evidence/audit1/report.json']
    buf=io.StringIO(newline='');csv.writer(buf,lineterminator='\n').writerow(row)
    index.write_bytes(before+(b'' if before.endswith(b'\n') else b'\n')+buf.getvalue().encode('utf-8'))
    print(json.dumps(dict(result='frozen',files=m['file_count'],bytes=m['bytes'],manifest_sha256=digest)))
else:
    m=load(root/'manifest.json');assert len(m['files'])==m['file_count']
    for row in m['files']:
        pth=root/row['path'];assert pth.stat().st_size==row['bytes'] and sha(pth)==row['sha256']
    assert load(root/'C_files_sha256.json')==c and load(root/'voice_files_sha256.json')==voices
    summary=load(repo/'research/fixed_source_profiles_v1_summary.json');assert summary['manifest_sha256']==sha(root/'manifest.json')
    rows=list(csv.reader(io.StringIO((repo/'handoff/阶段索引.csv').read_text(encoding='utf-8-sig'))))
    assert all(len(row)==8 for row in rows)
    matches=[row for row in rows if row[0]=='fixed_source_profiles_v1'];assert len(matches)==1 and matches[0][3]==summary['manifest_sha256']
    print(json.dumps(dict(result='verified',files=m['file_count'],C_H_unchanged=569,voices_unchanged=67)))

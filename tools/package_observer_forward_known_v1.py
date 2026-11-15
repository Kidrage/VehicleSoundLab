"""Freeze known forward controls and unchanged product contracts."""
import argparse,shutil,subprocess
from pathlib import Path
from research_archive_v1 import load,save,sha,freeze,verify,append_index


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True);a=p.parse_args()
    repo=Path(__file__).resolve().parents[1];e=a.workspace/'references/analysis/observer_forward_v1';root=a.workspace/'baselines/observer_forward_known_v1'
    parent=a.workspace/'baselines/quantile_surface_v1'
    assert sha(parent/'manifest.json')==load(repo/'research/quantile_surface_v1_summary.json')['manifest_sha256']
    known=load(e/'known1/report.json');audit=load(e/'known_audit1/report.json')
    assert known['result']=='observer_forward_known_ready' and audit['result']=='independent_observer_forward_known_passed' and audit['all7_verified']
    assert not known['material_read'] and not audit['material_read']
    assert audit['producer_sha256']==sha(e/'known1/report.json')
    assert audit['auditor_sha256']==sha(repo/'tools/audit_observer_forward_known_v1.py')==sha(e/'known_audit1/executed_audit.py')
    assert audit['oracle_sha256']==sha(repo/'tools/observer_forward_v1/audit_oracle.py')==sha(e/'known_audit1/executed_oracle.py')
    for name,digest in known['sources'].items():assert sha(repo/name)==sha(e/'known1/exact_sources'/name)==digest
    for row in known['cases']:assert sha(e/'known1'/row['file'])==row['sha256']
    protected={}
    for name,count in (('C_files_sha256.json',670),('voice_files_sha256.json',82),('F2_files_sha256.json',3)):
        values=load(parent/'evidence'/name);assert len(values)==count and all(sha(repo/n)==d for n,d in values.items())
        save(e/name,values);protected[name]=values
    names=set()
    for flags in (['ls-files','-z'],['ls-files','--others','--exclude-standard','-z']):names.update(subprocess.check_output(['git']+flags,cwd=repo).decode('utf-8').split('\0'))
    names.discard('');assert {n for n in names if Path(n).suffix in ('.c','.h')}==set(protected['C_files_sha256.json'])
    pm={r['path']:r['sha256'] for r in load(parent/'manifest.json')['files']}
    assert sha(repo/'handoff/C文件索引.csv')==pm['source/handoff/C文件索引.csv']
    hearings=load(parent/'validation.json')['protected_hearings_sha256'];assert all(sha(repo/n)==d for n,d in hearings.items())
    sources=[n for n in names if Path(n).suffix in ('.c','.h','.cmake','.in') or n.endswith('CMakeLists.txt')]
    sources+=list(protected['voice_files_sha256.json'])+list(protected['F2_files_sha256.json'])+list(hearings)
    sources+=[n for n in names if 'observer_forward' in n and Path(n).suffix in ('.py','.json','.md')]
    sources+=list(known['sources'])+['tools/research_archive_v1.py','tools/verify_research_archive_independent_v1.py',
        'tools/sound_dna/statistics.py','research/同窗前向算子已知控制V1.md','handoff/C文件索引.csv',
        'AGENTS.md','README.md','handoff/研究续接.md','handoff/开发留痕.md','handoff/当前代码阅读入口.md']
    validation=dict(result='observer_forward_known_frozen',known_controls=7,independent_audit=audit,
        original_observer_and_37_1024_exact_verified=True,underidentified_control_explicit=True,
        actual_material_inverse_not_started=True,native48k_or_C_or_timbre_qualified=False,
        C_H_exact=670,voice_parameters_exact=82,F2_files_exact=3,C_index_exact=True,protected_hearings_sha256=hearings,
        runtime_default_driver_owned_take_room_changed=False,downloaded=False,pushed=False,full_goal='active',
        next='All6 source native/warp inputs, regularized latent inference with conditioning/residual diagnostics, then sample-free temporal model reobserved validation.')
    inputs=dict(parent_manifest=parent/'manifest.json',parent_validation=parent/'validation.json',data_AGENTS=a.workspace/'AGENTS.md')
    shutil.copy2(__file__,e/'executed_package.py');result=freeze(root,repo,sources,e,inputs,validation);verify(root)
    save(repo/'research/observer_forward_known_v1_summary.json',dict(validation,**result))
    append_index(repo/'handoff/阶段索引.csv',['observer_forward_known_v1','baselines/observer_forward_known_v1/manifest.json',result['file_count'],result['manifest_sha256'],
        '7known/scalarOSC/directDFT/adjoint/null-control;no real inverse','670C-H82voice3F2/index exact;not a sound preset',
        'research/同窗前向算子已知控制V1.md | research/observer_forward_known_v1_summary.json','baselines/observer_forward_known_v1/validation.json'])
    print(dict(result='observer_forward_known_frozen',**result),flush=True)


if __name__=='__main__':main()

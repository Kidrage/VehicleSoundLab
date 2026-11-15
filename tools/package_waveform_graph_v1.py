"""Freeze failed nullspace, precision diagnosis and qualified small graph controls."""
import argparse
import shutil
import subprocess
from pathlib import Path
from research_archive_v1 import load,save,sha,freeze,verify,append_index


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace',type=Path,required=True);a=p.parse_args()
    repo=Path(__file__).resolve().parents[1];e=a.workspace/'references/analysis/waveform_nullspace_v1'
    audit=load(e/'summary_audit1/report.json')
    assert audit['result']=='independent_waveform_graph_summary_verified'
    assert audit['versions']['graph']['qualified']==12
    assert audit['auditor_sha256']==sha(repo/'tools/audit_waveform_graph_summary_v1.py')
    folders=('explicit1','explicit_audit1','known1','known_audit1','precision_diagnosis1','precision_audit1',
             'graph_explicit1','graph_explicit_audit1','graph_known1','graph_known_audit1','summary_audit1')
    parents={};inputs={}
    for n in ('observer_representer_v1','waveform_representer_v1'):
        root=a.workspace/'baselines'/n;s=load(repo/f'research/{n}_summary.json')
        assert sha(root/'manifest.json')==s['manifest_sha256']
        parents[n]=(root,{r['path']:r['sha256'] for r in load(root/'manifest.json')['files']})
        for f in ('manifest.json','validation.json'):inputs[f'upstream/{n}/{f}']=root/f
    parent,manifest=parents['waveform_representer_v1'];sources=set();protected={}
    for n,count in (('C_files_sha256.json',670),('voice_files_sha256.json',82),('F2_files_sha256.json',3)):
        values=load(parent/'evidence'/n)
        assert len(values)==count and all(sha(repo/path)==h for path,h in values.items())
        protected[n]=values;sources.update(values)
    paths=set()
    for flags in (['ls-files','-z'],['ls-files','--others','--exclude-standard','-z']):
        paths.update(subprocess.check_output(['git']+flags,cwd=repo).decode('utf-8').split('\0'))
    assert {n for n in paths if Path(n).suffix in ('.c','.h')}==set(protected['C_files_sha256.json'])
    assert sha(repo/'handoff/C文件索引.csv')==sha(parent/'source/handoff/C文件索引.csv')
    hearings=load(repo/'research/waveform_representer_v1_summary.json')['protected_hearings_sha256']
    assert all(sha(repo/n)==h for n,h in hearings.items());sources.update(hearings)
    locations={}
    def bind(name,expected):
        path=Path(name);assert sha(path)==expected
        if path.is_relative_to(e):
            rel=path.relative_to(e);assert rel.parts[0] in folders
            target='evidence/'+rel.as_posix()
        else:
            candidates=[(n,b,m) for n,(b,m) in parents.items() if path.is_relative_to(b)]
            if candidates:
                assert len(candidates)==1;n,b,m=candidates[0];rel=path.relative_to(b).as_posix()
            else:
                old=a.workspace/'references/analysis/waveform_representer_v1'
                assert path.is_relative_to(old)
                n='waveform_representer_v1';b,m=parents[n];rel='evidence/'+path.relative_to(old).as_posix()
            assert m[rel]==sha(b/rel)==expected
            key=f'upstream/{n}/{rel}';inputs[key]=b/rel;target='inputs/'+key
        locations[str(path)]=target
    for folder in folders:
        r=load(e/folder/'report.json')
        for name,expected in r.get('inputs',{}).items():bind(name,expected)
        if 'sources' in r:
            sources.update(r['sources'])
            for name,expected in r['sources'].items():
                if (e/folder/'exact_sources'/name).is_file():assert sha(e/folder/'exact_sources'/name)==expected
    # Preserve the prior comparison's reports, arrays and executed versions,
    # while retaining its larger complete archive as a manifest dependency.
    for folder in ('known2','known_audit2'):
        for path in (parent/'evidence'/folder).rglob('*'):
            if path.is_file():bind(str(path),sha(path))
    sources.update(n for n in paths if ('waveform_' in n and Path(n).suffix in ('.py','.json','.md')))
    sources.update(('research/零空间残差与三角修正V1.md','AGENTS.md','README.md','CMakeLists.txt',
        'handoff/C文件索引.csv','handoff/当前代码阅读入口.md','tools/research_archive_v1.py',
        'tools/verify_research_archive_independent_v1.py'))
    stage=e/'package1';stage.mkdir(exist_ok=False)
    for f in folders:shutil.copytree(e/f,stage/f)
    for n,values in protected.items():save(stage/n,values)
    shutil.copy2(__file__,stage/'executed_package.py');inputs['data_AGENTS.md']=a.workspace/'AGENTS.md'
    v=dict(result='waveform_graph_v1_frozen',results=audit['versions'],
        selected_terminal_evidence_directories=list(folders),original_input_archive_locations=locations,
        upstream_manifests_sha256={n:sha(b/'manifest.json') for n,(b,m) in parents.items()},
        C_H_exact=670,voice_parameters_exact=82,F2_files_exact=3,C_index_exact=True,
        protected_hearings_sha256=hearings,explicit_controls_per_version=7,finite_DFT_controls_per_version=4,
        original12_graph_qualified=12,original12_direct_normal_passed=4,independent_Decimal_diagnostic_cases=4,
        all36_summary_rows_verified=True,all_original_gates_unchanged=True,failed_nullspace_and_sources_retained=True,
        source_or_full_or_native48k_or_C_or_hearing_qualified=False,
        runtime_default_driver_owned_take_room_changed=False,old_68CTest_not_repeated=True,
        previous13GB_basis_not_copied=True,downloaded=False,pushed=False,full_goal='active')
    root=a.workspace/'baselines/waveform_graph_v1';result=freeze(root,repo,sources,stage,inputs,v);verify(root)
    save(repo/'research/waveform_graph_v1_summary.json',dict(v,**result))
    append_index(repo/'handoff/阶段索引.csv',['waveform_graph_v1','baselines/waveform_graph_v1/manifest.json',
        result['file_count'],result['manifest_sha256'],'same12 graph12/12;nullspace9/12 failure+4Decimal diagnoses',
        '670C-H82voice3F2/index exact;no source/full/C/audio promotion',
        'research/零空间残差与三角修正V1.md | research/waveform_graph_v1_summary.json',
        'baselines/waveform_graph_v1/validation.json'])
    print(result,flush=True)


if __name__=='__main__':main()

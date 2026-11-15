"""Freeze ONLY terminal adapters/preparation; never copy the live real fit."""
import argparse
from pathlib import Path
import shutil
import subprocess
from research_archive_v1 import load,save,sha,freeze,append_index


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace',type=Path,required=True)
    a=p.parse_args();repo=Path(__file__).resolve().parents[1]
    e=a.workspace/'references/analysis/waveform_file_real_adapter_v1'
    real=a.workspace/'references/analysis/waveform_file_real_v1'
    for name in ('prepare1','prepare_audit1'):shutil.copytree(real/name,e/name)
    folders=('known1','known_audit1','generic_audit1','generic_audit2','prepare1','prepare_audit1')
    reports={name:load(e/name/'report.json') for name in folders}
    assert reports['known1']['all_qualified'] and reports['known_audit1']['all_qualified']
    assert reports['generic_audit2']['all_qualified'] and reports['prepare_audit1']['all_qualified']
    assert reports['prepare_audit1']['producer_sha256']==sha(e/'prepare1/report.json')
    full=a.workspace/'baselines/waveform_file_full_v1'
    sources=set();versions={};inputs={};locations={}
    for file,count in (('C_files_sha256.json',670),('voice_files_sha256.json',82),('F2_files_sha256.json',3)):
        values=load(full/'evidence'/file)
        assert len(values)==count and all(sha(repo/n)==h for n,h in values.items())
        sources.update(values);save(e/file,values)
    hearings=load(repo/'research/waveform_file_full_v1_summary.json')['protected_hearings_sha256']
    assert all(sha(repo/n)==h for n,h in hearings.items());sources.update(hearings)
    def bind(name,digest):
        path=Path(name);assert sha(path)==digest,path
        if path.is_relative_to(e):target='evidence/'+path.relative_to(e).as_posix()
        elif path.is_relative_to(real/'prepare1'):target='evidence/prepare1/'+path.relative_to(real/'prepare1').as_posix()
        elif path.is_relative_to(real/'prepare_audit1'):target='evidence/prepare_audit1/'+path.relative_to(real/'prepare_audit1').as_posix()
        elif path.is_relative_to(repo):
            leaf='current/'+path.relative_to(repo).as_posix();inputs[leaf]=path;target='inputs/'+leaf
        else:
            assert path.is_relative_to(a.workspace)
            leaf='external/'+path.relative_to(a.workspace).as_posix();inputs[leaf]=path;target='inputs/'+leaf
        locations[str(path)]=target
    def factors(value):
        if isinstance(value,dict):
            if {'path','shape','file_bytes','sha256'}<=value.keys():bind(value['path'],value['sha256'])
            for x in value.values():factors(x)
        elif isinstance(value,list):
            for x in value:factors(x)
    for folder,r in reports.items():
        for name,digest in r.get('inputs',{}).items():bind(name,digest)
        for name,digest in r.get('sources',{}).items():
            assert sha(e/folder/'exact_sources'/name)==digest
            sources.add(name);versions.setdefault(name,{})[folder]=digest
        factors(r)
    for case in reports['known1']['cases']:
        factors(load(e/'known1'/case['report']))
    paths=set()
    for flags in (['ls-files','-z'],['ls-files','--others','--exclude-standard','-z']):
        paths.update(subprocess.check_output(['git']+flags,cwd=repo).decode('utf-8').split('\0'))
    sources.update(n for n in paths if n and 'waveform_file_real' in n and Path(n).suffix in ('.py','.md','.json'))
    sources.discard('research/waveform_file_real_adapter_v1_summary.json')
    sources.update(('research/原目标前后文适配V1.md','AGENTS.md','README.md','CMakeLists.txt',
        'handoff/C文件索引.csv','handoff/当前代码阅读入口.md','handoff/研究续接.md','handoff/开发留痕.md',
        'tools/research_archive_v1.py','tools/verify_research_archive_independent_v1.py'))
    bind(full/'manifest.json',sha(full/'manifest.json'))
    bind(full/'evidence/full1/report.json',sha(full/'evidence/full1/report.json'))
    inputs['data_AGENTS.md']=a.workspace/'AGENTS.md'
    shutil.copy2(__file__,e/'executed_package.py')
    metadata=dict(result='waveform_file_real_adapter_and_all_six_preparation_frozen',
        selected_terminal_evidence_directories=list(folders),original_input_archive_locations=locations,
        executed_source_versions=versions,current_source_sha256={n:sha(repo/n) for n in sources},
        protected_hearings_sha256=hearings,known_cases=reports['known_audit1']['cases'],
        preparation_cases=reports['prepare_audit1']['cases'],known_and_preparation_independently_qualified=True,
        C_H_exact=670,voice_parameters_exact=82,F2_files_exact=3,C_index_exact=True,
        real_fit_live_separate_not_archived=dict(pid=245372,tool_session=83157,directory=str(real/'real1')),
        no_C_or_hearing_or_sustained_voice_promotion=True,full_goal='active')
    root=a.workspace/'baselines/waveform_file_real_adapter_v1'
    summary=freeze(root,repo,sources,e,inputs,metadata)
    save(repo/'research/waveform_file_real_adapter_v1_summary.json',dict(metadata,**summary))
    append_index(repo/'handoff/阶段索引.csv',['waveform_file_real_adapter_v1','baselines/waveform_file_real_adapter_v1/manifest.json',
        summary['file_count'],summary['manifest_sha256'],'known4/original-target extension and all6 real preparation independently PASS',
        '670C-H82voice3F2/index/hearings exact;real6 live separately;no new voice',
        'research/原目标前后文适配V1.md | research/waveform_file_real_adapter_v1_summary.json',
        'baselines/waveform_file_real_adapter_v1/validation.json'])
    print(summary,flush=True)


if __name__=='__main__':main()

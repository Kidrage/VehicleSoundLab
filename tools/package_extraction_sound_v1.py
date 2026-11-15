"""Freeze terminal sound diagnostics, all failures, and immutable bindings only."""
import argparse
from pathlib import Path
import shutil
import subprocess
from research_archive_v1 import load,save,sha,freeze,append_index


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace',type=Path,required=True)
    a=p.parse_args();repo=Path(__file__).resolve().parents[1]
    evidence=a.workspace/'references/analysis/extraction_sound_v1'
    folders=('known1','known_audit1','roundoff1','known2','known_composed_audit1',
        'known_cases1','known_cases_audit1','known_cases_audit2')
    reports={name:load(evidence/name/'report.json') for name in folders}
    assert reports['known_audit1']['result']=='failed'
    assert reports['known_composed_audit1']['operator_and_frozen_series_aggregation_qualified']
    assert not reports['known_composed_audit1']['legacy_cross_operator_all_statistics_qualified']
    assert len(reports['known_composed_audit1']['legacy_normalized_failures'])==5
    assert reports['known_cases_audit2']['all_consumer_checks_passed']
    assert reports['known_cases_audit2']['producer_sha256']==sha(evidence/'known_cases1/report.json')
    assert len(reports['known_cases1']['guard_rejections'])==6
    full=a.workspace/'baselines/waveform_file_full_v1'
    sources=set();inputs={};locations={};versions={}
    for file,count in (('C_files_sha256.json',670),('voice_files_sha256.json',82),('F2_files_sha256.json',3)):
        protected=load(full/'evidence'/file)
        assert len(protected)==count and all(sha(repo/name)==digest for name,digest in protected.items())
        sources.update(protected);save(evidence/file,protected)
    hearings=load(repo/'research/waveform_file_full_v1_summary.json')['protected_hearings_sha256']
    assert all(sha(repo/name)==digest for name,digest in hearings.items());sources.update(hearings)
    def bind(name,digest):
        path=Path(name);assert sha(path)==digest,path
        if path.is_relative_to(evidence):target='evidence/'+path.relative_to(evidence).as_posix()
        elif path.is_relative_to(repo):
            leaf='current/'+path.relative_to(repo).as_posix();inputs[leaf]=path;target='inputs/'+leaf
        else:
            assert path.is_relative_to(a.workspace)
            # Only the immutable run specification may be copied from real1.
            live=a.workspace/'references/analysis/waveform_file_real_v1/real1'
            if path.is_relative_to(live):assert path==live/'run_spec.json'
            leaf='external/'+path.relative_to(a.workspace).as_posix();inputs[leaf]=path;target='inputs/'+leaf
        locations[str(path)]=target
    for folder,report in reports.items():
        for name,digest in report.get('inputs',{}).items():bind(name,digest)
        for name,digest in report.get('sources',{}).items():
            assert sha(evidence/folder/'exact_sources'/name)==digest
            sources.add(name);versions.setdefault(name,{})[folder]=digest
    for case in reports['known_cases1']['cases']:
        r=load(evidence/'known_cases1'/case['report'])
        for name,digest in r['inputs'].items():bind(name,digest)
        bind(r['source']['binding_file'],r['source']['binding_sha256'])
    paths=set()
    for flags in (['ls-files','-z'],['ls-files','--others','--exclude-standard','-z']):
        paths.update(subprocess.check_output(['git']+flags,cwd=repo).decode('utf-8').split('\0'))
    sources.update(name for name in paths if name and 'extraction_sound' in name and Path(name).suffix in ('.py','.md','.json'))
    sources.discard('research/extraction_sound_v1_summary.json')
    sources.update(('research/声纹提取的高频与左右诊断V1.md','AGENTS.md','README.md',
        'handoff/C文件索引.csv','handoff/当前代码阅读入口.md','handoff/研究续接.md','handoff/开发留痕.md',
        'tools/research_archive_v1.py','tools/verify_research_archive_independent_v1.py'))
    inputs['data_AGENTS.md']=a.workspace/'AGENTS.md'
    bind(full/'manifest.json',sha(full/'manifest.json'))
    shutil.copy2(__file__,evidence/'executed_package.py')
    metadata=dict(result='extraction_sound_known_composition_and_consumer_frozen',
        selected_terminal_evidence_directories=list(folders),original_input_archive_locations=locations,
        executed_source_versions=versions,current_source_sha256={name:sha(repo/name) for name in sources},
        protected_hearings_sha256=hearings,known_meter_cases=9,known_case_consumers=3,guard_rejections=6,
        original_failed_audit_preserved=True,legacy_cross_operator_all_statistics_qualified=False,
        legacy_normalized_failures=reports['known_composed_audit1']['legacy_normalized_failures'],
        independent_operator_and_frozen_series_statistics_qualified=True,
        consumer_independently_qualified_known_only=True,numerical_sensitivity_is_certified=False,
        C_H_exact=670,voice_parameters_exact=82,F2_files_exact=3,C_index_exact=True,
        real_fit_separate_not_archived=dict(pid=245372,tool_session=83157,
            directory=str(a.workspace/'references/analysis/waveform_file_real_v1/real1')),
        no_C_or_hearing_or_sustained_voice_promotion=True,full_goal='active')
    root=a.workspace/'baselines/extraction_sound_v1'
    summary=freeze(root,repo,sources,evidence,inputs,metadata)
    save(repo/'research/extraction_sound_v1_summary.json',dict(metadata,**summary))
    append_index(repo/'handoff/阶段索引.csv',['extraction_sound_v1','baselines/extraction_sound_v1/manifest.json',
        summary['file_count'],summary['manifest_sha256'],'known9 operator+frozen statistics and3audited case consumers PASS;5tiny normalized failures retained',
        '670C-H82voice3F2/index/hearings exact;real6 remains live separately;no voice',
        'research/声纹提取的高频与左右诊断V1.md | research/extraction_sound_v1_summary.json',
        'baselines/extraction_sound_v1/validation.json'])
    print(summary,flush=True)


if __name__=='__main__':main()

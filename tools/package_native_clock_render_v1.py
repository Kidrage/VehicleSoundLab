"""Freeze terminal known native rendering and all six actual preparations."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
from research_archive_v1 import load,save,sha,freeze,append_index


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace',type=Path,required=True);a=p.parse_args()
    for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    repo=Path(__file__).resolve().parents[1]
    e=a.workspace/'references/analysis/native_clock_render_v1'
    folders=('known1','known_audit1','prepare1','prepare_audit1')
    reports={name:load(e/name/'report.json') for name in folders}
    assert reports['known_audit1']['all_known_qualified'] and len(reports['known_audit1']['cases'])==13
    assert reports['prepare_audit1']['all_preparation_qualified'] and len(reports['prepare_audit1']['cases'])==6
    assert reports['known_audit1']['producer_sha256']==sha(e/'known1/report.json')
    assert reports['prepare_audit1']['producer_sha256']==sha(e/'prepare1/report.json')
    full=a.workspace/'baselines/waveform_file_full_v1'
    sources=set();inputs={};locations={};versions={}
    for file,count in (('C_files_sha256.json',670),('voice_files_sha256.json',82),('F2_files_sha256.json',3)):
        protected=load(full/'evidence'/file)
        assert len(protected)==count and all(sha(repo/name)==digest for name,digest in protected.items())
        sources.update(protected);save(e/file,protected)
    hearings=load(repo/'research/waveform_file_full_v1_summary.json')['protected_hearings_sha256']
    assert all(sha(repo/name)==digest for name,digest in hearings.items());sources.update(hearings)
    def bind(name,digest):
        path=Path(name);assert sha(path)==digest,path
        if path.is_relative_to(e):target='evidence/'+path.relative_to(e).as_posix()
        elif path.is_relative_to(repo):
            leaf='current/'+path.relative_to(repo).as_posix();inputs[leaf]=path;target='inputs/'+leaf
        else:
            assert path.is_relative_to(a.workspace)
            live=a.workspace/'references/analysis/waveform_file_real_v1/real1'
            if path.is_relative_to(live):assert path==live/'run_spec.json'
            leaf='external/'+path.relative_to(a.workspace).as_posix();inputs[leaf]=path;target='inputs/'+leaf
        locations[str(path)]=target
    for folder,r in reports.items():
        for name,digest in r.get('inputs',{}).items():bind(name,digest)
        for name,digest in r.get('sources',{}).items():
            assert sha(e/folder/'exact_sources'/name)==digest
            sources.add(name);versions.setdefault(name,{})[folder]=digest
    published=[]
    for c in reports['prepare1']['cases']:
        with np.load(e/'prepare1'/c['file']) as z:
            raw=z['raw_broad_mean_power']
            published.append(dict(label=c['label'],source_cutoff_hz=c['source_cutoff_hz'],
                raw_14to24k_fraction=float(raw[5].sum()/raw.sum()),
                raw_total_mean_power_FS2=float(raw.sum()),raw_14to24k_mean_power_FS2=raw[5].tolist(),
                FIR_only_band_power_change_dB=c['source_FIR_only_signed_changes']['broad']['power_change_dB']))
    save(e/'native_source_band_summary.json',published)
    paths=set()
    for flags in (['ls-files','-z'],['ls-files','--others','--exclude-standard','-z']):
        paths.update(subprocess.check_output(['git']+flags,cwd=repo).decode('utf-8').split('\0'))
    sources.update(name for name in paths if name and 'native_clock' in name and Path(name).suffix in ('.py','.md','.json'))
    sources.discard('research/native_clock_render_v1_summary.json')
    sources.update(('research/原生48k逆时钟渲染V1.md','AGENTS.md','README.md',
        'handoff/C文件索引.csv','handoff/当前代码阅读入口.md','handoff/研究续接.md','handoff/开发留痕.md',
        'tools/research_archive_v1.py','tools/verify_research_archive_independent_v1.py'))
    inputs['data_AGENTS.md']=a.workspace/'AGENTS.md'
    bind(full/'manifest.json',sha(full/'manifest.json'))
    shutil.copy2(__file__,e/'executed_package.py')
    metadata=dict(result='native_clock_known_and_actual_preparation_frozen',
        selected_terminal_evidence_directories=list(folders),original_input_archive_locations=locations,
        executed_source_versions=versions,current_source_sha256={name:sha(repo/name) for name in sources},
        protected_hearings_sha256=hearings,known_cases=13,input_rejections=10,actual_preparations=6,
        all_known_and_preparations_independently_qualified=True,native_source_band_summary=published,
        raw14kplus_is_tiny_for_these_six_only=True,actual_fitted_native_render_qualified=False,
        C_H_exact=670,voice_parameters_exact=82,F2_files_exact=3,C_index_exact=True,
        real_fit_separate_not_archived=dict(pid=245372,tool_session=83157,
            directory=str(a.workspace/'references/analysis/waveform_file_real_v1/real1')),
        previous_goal_turn_classification='Progress: adca620 sound-domain qualification; current native controls and actual source preparation add evidence.',
        no_C_or_hearing_or_sustained_voice_promotion=True,full_goal='active')
    root=a.workspace/'baselines/native_clock_render_v1'
    summary=freeze(root,repo,sources,e,inputs,metadata)
    save(repo/'research/native_clock_render_v1_summary.json',dict(metadata,**summary))
    append_index(repo/'handoff/阶段索引.csv',['native_clock_render_v1','baselines/native_clock_render_v1/manifest.json',
        summary['file_count'],summary['manifest_sha256'],'13known native renderer+10guards and6actual interval/sourceFIR preparations independentlyPASS',
        '670C-H82voice3F2/index/hearings exact;actual fit stilllive;no source/C promotion',
        'research/原生48k逆时钟渲染V1.md | research/native_clock_render_v1_summary.json',
        'baselines/native_clock_render_v1/validation.json'])
    print(summary,flush=True)


if __name__=='__main__':main()

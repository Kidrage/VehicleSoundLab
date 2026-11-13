"""Freeze complete isolated C fine-static source with failures, sample/timing evidence and indices."""
import argparse,csv,io,subprocess
from pathlib import Path
from research_archive_v1 import sha,load,save,freeze,verify,append_index
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--stage',choices=['index','freeze','verify'],required=True);a=p.parse_args()
repo=Path(__file__).resolve().parents[1];parent=a.workspace/'baselines/modal_texture_c_v1'
evidence=a.workspace/'references/analysis/spectral_texture_c_v1';root=a.workspace/'baselines/spectral_texture_c_v1'
old=load(parent/'inputs/C_files_sha256.json');voices=load(parent/'inputs/voice_files_sha256.json')
names=subprocess.check_output(['git','ls-files','-z'],cwd=repo).decode().split('\0')
names+=subprocess.check_output(['git','ls-files','--others','--exclude-standard','-z'],cwd=repo).decode().split('\0')
c={name:sha(repo/name) for name in sorted(set(names)) if name and Path(name).suffix.lower() in ['.c','.h']}
assert len(old)==579 and len(c)==591 and all(c[name]==digest for name,digest in old.items())
assert len(voices)==67 and all(sha(repo/name)==digest for name,digest in voices.items())
new=set(c)-set(old);assert len(new)==12;index=repo/'handoff/C文件索引.csv'


def rows():
    result=list(csv.reader(io.StringIO(index.read_text(encoding='utf-8-sig'))))
    assert all(len(row)==5 for row in result);return {row[0]:row for row in result[1:]}


if a.stage=='index':
    before=rows();assert len(before)==579 and all(before[name][4]==digest for name,digest in old.items())
    roles={'fft':'只读FFT计划／512点原地变换','filter':'拥有编译核／独立历史环与256帧因果分块卷积',
        'profile':'固定谱形参数的有限数值域校验','voice':'拥有编译核／新高斯激励／预热及分带Stereo持续输出',
        'io':'独立非实时严格读取，失败保留原输出','checks':'直接DFT／卷积／同址／拥有参数／新声源契约',
        'probe':'完整C主声线与细谱分轨／非对齐控制／回调尺寸成本'}
    stream=io.StringIO(newline='');writer=csv.writer(stream,lineterminator='\n')
    for name in sorted(new):
        module=Path(name).parts[1]
        writer.writerow([name,'细谱持续生成' if module=='spectral_texture' else '分块卷积／独立核查',module,roles[Path(name).stem],c[name]])
    before_bytes=index.read_bytes();assert before_bytes.endswith(b'\n');index.write_bytes(before_bytes+stream.getvalue().encode())
    print(dict(total=591,unchanged=579,added=12));raise SystemExit

assert len(rows())==591 and all(rows()[name][4]==digest for name,digest in c.items())
if a.stage=='freeze':
    reports={f'verify{i}':load(evidence/f'verify{i}/report.json') for i in range(1,4)}
    assert reports['verify1']['result']=='failed' and reports['verify2']['result']=='failed'
    final=reports['verify3'];assert final['result']=='full_isolated_C_fine_static_idle_passed_pending_listening'
    assert final['tests']==4 and final['comparisons_count']==30 and final['blocks1_479_exact']
    assert final['old_C_and_voice_files_unchanged']=={'C_files_sha256.json':579,'voice_files_sha256.json':67}
    source=set(final['sources'])
    for name,digest in final['sources'].items():
        assert sha(repo/name)==sha(evidence/'verify3/exact_sources'/name)==digest,name
    for label,report in reports.items():
        for name,digest in report['sources'].items():assert sha(evidence/label/'exact_sources'/name)==digest
    profile=repo/'experiments/spectral_texture_v1/F2_fine_static.sfir'
    assert sha(profile)==sha(evidence/'verify3/F2/fine.sfir')
    five=[row for row in final['timing'] if row['id'].startswith('F2_') or row['id']=='sustained_30s']
    assert len(five)==10 and sum(row['chunks'] for row in five)==27600 and all(row['overruns']==0 for row in five)
    single=next(row for row in final['timing'] if row['id']=='controls_1')
    sustained=next(row for row in five if row['id']=='sustained_30s')
    source.update(['tools/package_spectral_texture_c_v1.py','research/怠速细谱持续C生成V1.md',
        'modules/partitioned_fir/README.md','modules/spectral_texture/README.md',
        'experiments/spectral_texture_v1/F2_fine_static.sfir','AGENTS.md','handoff/算法说明.md',
        'handoff/C模块与接口.md','handoff/C文件索引.csv','handoff/开发留痕.md','handoff/研究续接.md'])
    save(evidence/'C_files_sha256.json',c);save(evidence/'voice_files_sha256.json',voices)
    inputs={'C_files_sha256.json':evidence/'C_files_sha256.json','voice_files_sha256.json':evidence/'voice_files_sha256.json',
        'parent_manifest.json':parent/'manifest.json','data_workspace_AGENTS.md':a.workspace/'AGENTS.md',
        'modal_profile.json':a.workspace/'baselines/modal_texture_v1/evidence/trial1/profile.json',
        'fine_profile.json':a.workspace/'baselines/fixed_source_profiles_v1/evidence/trial1/F2_tailpipe/profile.json'}
    validation=dict(schema='vsl.spectral-texture-c-freeze/1',result='isolated_full_C_fine_static_source_passed_pending_listening',
        git_parent=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),previous_goal_turn='progress',
        C_H_total=591,C_H_unchanged=579,C_H_added=12,voice_files_unchanged=67,tests=4,old59_repeated=False,
        fixed_source_parameters_exact=True,kernels=6,taps_per_kernel=8192,partition_frames=256,FFT_frames=512,
        warmup_frames=48000,all_C_core_detail_mix=True,full_frozen_groups=9,known_groups=1,sample_comparisons=30,
        maximum_FS_error=final['maximum_FS_error'],controls1_479_WAV_exact=True,detail_control_independent=True,
        sustained_seconds=30,sustained_prefix_exact=True,callback_5ms_count=27600,callback_5ms_overruns=0,
        callback_5ms_worst_seconds=max(row['worst_chunk_seconds'] for row in five),
        sustained_compute_seconds=sustained['compute_seconds'],single_sample_budget_overruns=single['overruns'],
        timing_scope='Isolated source compute only;not complete driver/device or hard realtime. Internal prefetch is not external input zero latency.',
        failed_attempts=['verify1_unsigned_test_fixture','verify2_unjustified_L1_domain_reject'],final_attempt='verify3',
        original_profile_destroyed_after_compile=True,driver_integrated=False,default_UI_takes_changed=False,
        room=False,phase_FM=False,detail_AM=False,listening_accepted=False,actual_RPM_load=False,
        shared_phase_qualified=False,physical_7_1_4_verified=False,old_binaries_preserved=True,
        listening_url='http://127.0.0.1:8789/references/analysis/modal_texture_v1/review1/index.html',
        next='Existing listening selection,then optional typed idle/owned take integration and complete callback/device cost;preserve one driver,moving35 and source/RPM limits.')
    info=freeze(root,repo,source,evidence,inputs,validation)
    save(repo/'research/spectral_texture_c_v1_summary.json',dict(validation,freeze='baselines/spectral_texture_c_v1',**info))
    append_index(repo/'handoff/阶段索引.csv',['spectral_texture_c_v1','baselines/spectral_texture_c_v1/manifest.json',
        str(info['file_count']),info['manifest_sha256'],'Full isolated C fine-static source;4CTest;9frozen groups;block/control/timing checks',
        'Listening pending;no driver/device/hardRT adoption;1sample overruns retained;579C-H/67voices unchanged',
        'research/怠速细谱持续C生成V1.md | research/spectral_texture_c_v1_summary.json',
        'baselines/spectral_texture_c_v1/validation.json | baselines/spectral_texture_c_v1/evidence/verify3/report.json'])
    print(info)
else:
    manifest=verify(root);summary=load(repo/'research/spectral_texture_c_v1_summary.json')
    assert summary['manifest_sha256']==sha(root/'manifest.json')
    assert load(root/'inputs/C_files_sha256.json')==c and load(root/'inputs/voice_files_sha256.json')==voices
    assert sha(root/'source/tools/package_spectral_texture_c_v1.py')==sha(Path(__file__))
    print(dict(verified=manifest['file_count'],C_H=591,voices=67))

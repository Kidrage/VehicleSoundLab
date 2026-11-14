"""Close the weak FIR trial and actual driver timing study without adopting either."""
import argparse,csv,io,shutil,subprocess
from pathlib import Path
from research_archive_v1 import load,save,sha,freeze,verify,append_index

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--stage',choices=['freeze','verify'],required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
root=a.workspace/'baselines/fir_mac_v1'
if a.stage=='verify':
    print(verify(root)['file_count']);raise SystemExit
evidence=a.workspace/'references/analysis/fir_mac_v1'
old=load(evidence/'before1/C_files_sha256.json')
voices=load(evidence/'before1/voice_files_sha256.json')
assert len(old)==612 and len(voices)==67
assert all(sha(repo/k)==v for k,v in {**old,**voices}.items())
trial=load(evidence/'verify1/report.json');driver=load(evidence/'stage_run1/report.json')
assert trial['result']=='paired_FIR_exactness_and_cost_observed' and not trial['useful_cost_reduction']
assert driver['result']=='actual_driver_stages_observed_with_exact_audio'
assert load(evidence/'production_restored.json')['CMake_original']
assert sha(repo/'modules/partitioned_fir/CMakeLists.txt')==sha(evidence/'before1/source/modules/partitioned_fir/CMakeLists.txt')
assert sha(evidence/'verify1/paired.csv')==trial['paired_trace_sha256']
assert len(list(csv.DictReader((evidence/'verify1/paired.csv').open())))==6000
# The first executed experiment lived in production paths. Those bytes are
# archived, not falsely compared against the deliberately restored source tree.
for name,digest in trial['sources'].items():
    assert sha(evidence/'verify1/exact_sources'/name)==digest,name
for name,digest in driver['sources'].items():
    assert sha(repo/name)==digest==sha(evidence/'stage_run1/exact_sources'/name),name
for row in driver['cases']:
    x=evidence/'stage_run1'/row['plain']['raw_file']
    y=evidence/'stage_run1'/row['timed']['raw_file']
    assert x.stat().st_size==1152000*4 and x.read_bytes()==y.read_bytes()
    for kind in ['plain','timed']:
        assert sha(evidence/'stage_run1'/row[kind]['raw_file'])==row[kind]['raw_sha256']
        assert sha(evidence/'stage_run1'/row[kind]['trace_file'])==row[kind]['trace_sha256']
proof=evidence/'relocated_build_proof2';proof.mkdir(exist_ok=False)
for name in ['CMakeCache.txt','Testing/Temporary/LastTest.log']:
    target=proof/Path(name).name;shutil.copy2(repo/'build-fir-mac-v1'/name,target)
log=(proof/'LastTest.log').read_bytes()
assert log.count(b'Test Passed.')==2
for name in ['fir_optimized_checks.exe','fir_scalar_checks.exe']:
    shutil.copy2(repo/'build-fir-mac-v1/Release'/name,proof/name)
for path in [*(repo/'experiments/fir_mac_v1').iterdir(),*(repo/'experiments/driver_stage_cost_v1').iterdir()]:
    if path.is_file():
        target=proof/'source'/path.relative_to(repo);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)

index=repo/'handoff/C文件索引.csv'
before=index.read_bytes();rows=list(csv.reader(io.StringIO(before.decode('utf-8-sig'))))
assert rows[0]==['文件','模块','构建归属','职责','SHA-256'] and len(rows)==601
for row in rows[1:]:assert sha(repo/row[0])==row[4]
names=set(old)
new=[]
# The prior index lagged the actual frozen source identity by twelve entries.
# Add those existing files honestly before the seven new experiment files.
indexed={row[0] for row in rows[1:]}
missing=sorted(names-indexed);assert len(missing)==12
for name in missing:
    assert name.startswith(('modules/spectral_motion/','experiments/idle_microtexture_v1/'))
    new.append([name,'既有怠速快速细节','已归档可选怠速模块／实验',
        '补齐历史索引遗漏；源码与原612身份逐字节相同',sha(repo/name)])
for folder,tag,role in [
    ('experiments/fir_mac_v1','独立FIR成本实验','原卷积与SSE2／scalar精确性及配对成本；未晋级生产'),
    ('experiments/driver_stage_cost_v1','独立驾驶阶段计时','原驾驶链调用计时／输出字节对照；含测量开销')]:
    for path in sorted((repo/folder).iterdir()):
        if path.suffix in ['.c','.h']:
            name=path.relative_to(repo).as_posix();assert name not in names
            names.add(name);new.append([name,tag,'独立CMake实验',role,sha(path)])
assert len(new)==19 and len(names)==619
buf=io.StringIO(newline='');csv.writer(buf,lineterminator='\n').writerows(new)
index.write_bytes(before+buf.getvalue().encode('utf-8'))
sources=set(driver['sources'])
for folder in ['experiments/fir_mac_v1','experiments/driver_stage_cost_v1']:
    sources.update(p.relative_to(repo).as_posix() for p in (repo/folder).iterdir() if p.is_file())
sources.update(['tools/package_fir_mac_v1.py','tools/package_fir_mac_v1_2.py','tools/verify_fir_mac_v1.py','research/fir_mac_v1_plan.json',
    'research/driver_stage_cost_v1_plan.json','research/实时链成本定位V1.md','handoff/C文件索引.csv',
    'AGENTS.md','handoff/研究续接.md','handoff/开发留痕.md'])
validation=dict(schema='vsl.fir-and-driver-cost-freeze/1',result='weak_MAC_trial_retained_production_restored_actual_driver_profiled',
    parent_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
    original612C_H_exact=True,old67voices_exact=True,new_experimental_C_H=7,total_indexed_C_H=619,
    first_packaging_index_count_failure_preserved=True,historical12missing_index_rows_added=True,
    initial_executed_sources_preserved=True,relocated_optimized_and_scalar_contracts_passed=True,
    paired_blocks=6000,useful_5percent_threshold_met=False,production_adopted=False,
    driver_cases=[dict(case=r['case'],plain_seconds=r['plain']['total_seconds'],audio_seconds=12,
      max_block_ms=r['plain']['max_ms'],exceedances=r['plain']['budget_exceedances'],
      stages=r['ordered_stages'],all1152000_float_samples_exact=True) for r in driver['cases']],
    measurement_overhead_not_subtracted=True,stage_costs_not_unbiased_plain_fractions=True,
    pending_idle_candidate_changed=False,hard_realtime=False,
    next='Idle source extraction/listening remains the priority. CPU work identifies main OSC as a later target, not a timbre fix; no blind tuning of pending phase candidate or promotion to C/defaults. Full goal remains active.')
inputs={'original_C_files_sha256.json':evidence/'before1/C_files_sha256.json',
        'original_voice_files_sha256.json':evidence/'before1/voice_files_sha256.json',
        'data_workspace_AGENTS':a.workspace/'AGENTS.md'}
result=freeze(root,repo,sources,evidence,inputs,validation);verify(root)
save(repo/'research/fir_mac_v1_summary.json',dict(validation,**result))
append_index(repo/'handoff/阶段索引.csv',['fir_mac_v1','baselines/fir_mac_v1/manifest.json',result['file_count'],
    result['manifest_sha256'],'6000paired/all6FIR/exactdouble/relocated2contracts;actual12s idle+drive exactfloat',
    'MAC1..3percent/noadoption;stageQPCoverhead/plainblockoverruns;612C-H67voicesunchanged',
    'research/实时链成本定位V1.md | research/fir_mac_v1_summary.json','baselines/fir_mac_v1/validation.json'])
print(result)

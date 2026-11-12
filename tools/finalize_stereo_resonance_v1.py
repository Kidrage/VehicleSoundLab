"""Bind the candidate, all technical evidence and C-file index for handoff."""
import argparse,csv,json,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for name in ('workspace','fit','verification','review','out'):p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
from drive_evidence_v1.sources import sha
v=json.loads((a.verification/'report.json').read_text(encoding='utf-8'))
f=json.loads((a.fit/'report.json').read_text(encoding='utf-8'))
review=json.loads((a.review/'report.json').read_text(encoding='utf-8'))
assert v['result']=='stereo_candidate_technical_pass' and review['result']=='review_technical_pass'
assert sha(a.fit/'report.json')==v['fit_report_sha256']==review['inputs'][str(a.fit/'report.json')]
for name,digest in v['sources'].items():assert sha(repo/name)==digest==sha(a.verification/'exact_sources'/name),name
for name,digest in v['evidence_sha256'].items():assert sha(a.verification/name)==digest,name
for name,digest in f['sources'].items():assert sha(repo/name)==digest,name
for name,digest in f['inputs'].items():assert sha(Path(name))==digest,name
for name,digest in review['sources'].items():assert sha(repo/name)==digest,name
for row in review['clips']:assert sha(a.review/row['file'])==row['sha256']
assert sha(a.review/'index.html')==review['page_sha256']
assert sha(a.fit/'A cabin settle.sres')==f['profile_sha256']
a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_finalize.py')
with (a.verification/'prior_C_index.csv').open(encoding='utf-8-sig') as stream:rows=list(csv.DictReader(stream))
assert len(rows)==521
for row in rows:assert sha(repo/row['文件'])==row['SHA-256'],row['文件']
roles={
 'modules/stereo_resonance/profile.h':('立体声连续共振','stereo_resonance','不可变双通道VAR／创新协方差／稳定证书参数'),
 'modules/stereo_resonance/profile.c':('立体声连续共振','stereo_resonance','非实时参数／SOS／Lyapunov严格稳定校验'),
 'modules/stereo_resonance/voice.h':('立体声连续共振','stereo_resonance','借用参数的持续声源／独立量接口，无RPM时钟'),
 'modules/stereo_resonance/voice.c':('立体声连续共振','stereo_resonance','双通道跨延迟递推／新随机激励／带通／量平滑'),
 'modules/stereo_resonance_io/profile.h':('立体声参数IO','stereo_resonance_io','独立非实时文本加载接口'),
 'modules/stereo_resonance_io/profile.c':('立体声参数IO','stereo_resonance_io','事务解析与校验，失败保持目标不变'),
 'experiments/stereo_resonance_v1/probe.c':('立体声离线宿主','VslStereoResonance_probe','持续double分轨导出与独立512帧计时，无设备'),
 'experiments/stereo_resonance_v1/checks.c':('立体声契约','VslStereoResonance_checks','多阶跨通道／SOS／预热／静音／非法证书及事务IO核查')}
for name,role in roles.items():rows.append(dict(zip(rows[0],(name,*role,sha(repo/name)))))
index=repo/'handoff/C文件索引.csv'
with index.open('w',encoding='utf-8-sig',newline='') as stream:
    writer=csv.DictWriter(stream,fieldnames=list(rows[0]),lineterminator='\n');writer.writeheader();writer.writerows(rows)
assert len(rows)==529
voice=repo/'voices/stereo_resonance_v1';voice.mkdir(exist_ok=True)
shutil.copy2(a.fit/'A cabin settle.sres',voice/'A cabin settle.sres')
inspection=a.workspace/'references/analysis/idle_target_v2/inspect1'
ir=json.loads((inspection/'report.json').read_text(encoding='utf-8'))
source=ir['sources']['E'];assert sha(Path(source['video']))==source['video_sha256']
for frame in source['frames']:assert sha(inspection/'E'/frame['file'])==frame['sha256']
annotation=dict(schema='vsl.idle-target-observation/1',date='2026-11-12',
    inspection_report_sha256=sha(inspection/'report.json'),video_sha256=source['video_sha256'],
    inspected_boards=['E/board_1.jpg','E/board_2.jpg','E/board_3.jpg'],frames=len(source['frames']),
    observation=[
        dict(seconds=[45.867,46.267],gear_display=1,speed_display_kmh=0,
             tach_description='Pointer rises from approximately1500..2000 through about3700RPM; visually read, not ECU telemetry'),
        dict(seconds=[46.4,47.6],gear_display=1,speed_display_kmh=0,
             tach_description='Pointer near4500RPM; stationary elevated-rev staging, not stable idle'),
        dict(seconds=47.733,gear_display=1,dash_speed_kmh=0,phone_speed_kmh=1),
        dict(seconds=47.867,gear_display=1,dash_speed_kmh=7,phone_speed_kmh=4),
        dict(seconds=48,gear_display=1,dash_speed_kmh=17,phone_speed_kmh=11,
             tach_description='Pointer approximately5600RPM')],
    decision='Exclude E46..47 as idle. Keep as stationary staging-to-launch context only.',
    not_established=['Actual pedal/brake/clutch/load/boost/fueling inputs','Activation of launch/thrust control',
                     'ECU RPM accuracy, dash/phone latency or calibrated audio/video offset'])
(repo/'research/idle_target_v2_annotations.json').write_text(json.dumps(annotation,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
summary=dict(schema='vsl.stereo-resonance-summary/1',date='2026-11-12',result=v['result'],
    C_H_rows=529,unchanged_prior_C_H=521,new_C_H=8,Ctests_passed=52,C_H_index_sha256=sha(index),
    source_seconds=f['source_seconds'],source_context='A startup-settling cabin; not confirmed warm idle/exterior',
    main_model_unchanged=True,DNA_first8s_exact_to_frozen=v['DNA_first8s_exact_to_frozen'],
    profile_path='voices/stereo_resonance_v1/A cabin settle.sres',profile_sha256=f['profile_sha256'],
    fitted_bands=[m['band_hz'] for m in f['models']],skipped=f['skipped'],
    controls=v['controls'],continuous_C_trials=[dict(seed=t['seed'],frames=t['frames'],
        supported_max_power_error_db=t['supported_max_power_error_db'],
        supported_max_coherence_error=t['supported_max_coherence_error'],
        low20_300_change_db=t['low20_300_change_db'],peak_raw_FS=t['peak_raw_FS'],
        performance=t['performance']) for t in v['trials']],
    maximum_C_theory_power_error_db=max(abs(x) for t in v['trials'] for b in t['C_vs_theory'] for x in b['power_db']),
    maximum_C_theory_coherence_error=max(b['coherence_error'] for t in v['trials'] for b in t['C_vs_theory']),
    maximum_reference_half_drift_db=max(abs(x) for b in v['reference_half_drift'] for x in b['power_delta_db']),
    review_url=review['url'],review_files=len(review['clips']),
    listening_accepted=False,driver_integrated=False,native_integrated=False,
    new_room=False,new_source_or_RPM_calibration=False,full_idle_or_acceleration_calibrated=False,
    limits=v['limits'],evidence_sha256={
        path.relative_to(a.workspace).as_posix():sha(path) for path in
        [a.fit/'report.json',a.verification/'report.json',a.review/'report.json',inspection/'report.json']})
for target in (a.out/'summary.json',repo/'research/stereo_resonance_v1_summary.json'):
    target.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(result=summary['result'],C_H=529,Ctests=52,profile_sha256=f['profile_sha256'])))

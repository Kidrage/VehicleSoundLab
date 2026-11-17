"""Preserve approved A inspection as a diagnostic workbench project, without a fit."""
import argparse
import base64
from html import escape
import json
from pathlib import Path
from event_authoring.audio import sha
from event_designer.workspace import EventWorkspace
from event_designer.package import write_json


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    repo=Path(__file__).resolve().parents[1];data=Path('E:/VehicleSoundLab')
    evidence=data/'references/analysis/A_exterior_event_v1'
    scan=json.loads((evidence/'scan1/report.json').read_text(encoding='utf-8'))
    assert scan['source_id']=='A' and len(scan['candidates'])==92
    assert sha(Path(scan['source']))==scan['source_sha256']
    source=evidence/'timeline1/A_346_context/original.wav'
    ws=EventWorkspace(repo,data/'designs/events')
    p=ws.create(dict(filename='A_342_to_351_cabin_context.wav',
        audio=base64.b64encode(source.read_bytes()).decode(),kind='afterfire',viewpoint='cabin'))
    note=('已批准A原录音342–351秒；局部4.72秒对应原片346.72秒。'
        '342–343秒画面为尾排，344秒后已切至车内；附近声谱有连续升速。'
        '此瞬态的前后背景全频对比均超过3 dB，但物理身份不明，未确认为回火。'
        'afterfire只是待设计的目标槽，不是素材分类结论；本工程不生成或替换音色参数。')
    p=ws.save(dict(id=p['id'],name='A346.72 未分类瞬态 · 车内核查',context=note))
    p=ws.scan_candidates(dict(id=p['id']))
    assert len(p['candidate_scan']['candidates'])==2 and p['candidate_scan']['both_above_3db']==1
    p=ws.use_candidate(dict(id=p['id'],scan_run=p['scan_run'],candidate_index=1))
    assert p['document'] is None and p['context_matches_selection']
    report=dict(schema='vsl.A-exterior-event-review/1',source_id='A',
        source_sha256=scan['source_sha256'],original_seconds=[342,351],project_id=p['id'],
        project_name=p['name'],project_root=str(ws.root/p['id']),
        scan_requested_seconds=150,scan_total=92,scan_both_backgrounds=1,
        visual_inspection=[
            dict(case='A_stationary_rev_context',observed='Rear exterior stationary rev sequence; edit to side/interior at249s.'),
            dict(case='A_road_context',observed='Alternating tailpipe and cabin shots; recording perspective is not uniformly exterior.'),
            dict(case='A_346_context',observed='Tailpipe at342/343s, cabin by344s;346.72s is cabin context, nearby continuous rising harmonic tracks.')],
        selected_event=p['selected_candidate'],context_probe=p['context_probe'],
        original_audio_monitor_gain=.25,fit_performed=False,physical_identity_confirmed=False,
        formal_profile_promoted=False,runtime_C_changed=False,goal_complete=False)
    write_json(args.output/'report.json',report)
    page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>事件候选核查 · A</title><style>body{background:#111a17;color:#dce8df;font:16px system-ui;margin:auto;max-width:1000px;padding:30px 20px}h1{font-size:28px}p{line-height:1.7;color:#b4c5bb}section{background:#1c2923;border:1px solid #35483d;padding:20px;border-radius:12px;margin:20px 0}img{max-width:100%;height:auto}audio,select{width:100%;margin:12px 0}select{padding:12px;background:#16221c;color:#e1eadf}a{color:#c1e995}small{color:#a7baad}code{overflow-wrap:anywhere}</style>
<h1>先找到动作，再设计事件音色。</h1><p>本轮核查已批准A素材中的150秒，共92处候选。只有346.72秒一处同时高于前后背景，但它处于车内画面和升速语境，尚不能确认是回火。本页只有原录音，没有新增合成音色。</p>
<section><h2>听原声上下文</h2><select id="clip"><option value="../timeline1/A_346_context/monitor.wav">原片342–351秒 · 保留画面切换上下文</option><option value="CONTEXT">346.72秒候选及固定前后背景 · 0.71秒</option></select><audio id="player" controls preload="metadata" src="../timeline1/A_346_context/monitor.wav"></audio><small>固定−12 dB监听；没有清洗、归一化、均衡或混响。</small><p>PROJECT</p></section>
<section><h2>附近画面</h2><img src="../timeline1/A_346_context/dashboard.jpg" alt="342至351秒画面：尾排切至车内"><p>视频画面仅用于动作和视角核查；未标定ECU、踏板或精确音画时延。</p></section>
<section><h2>工作台新增入口</h2><img src="../verification1/ui/desktop-candidates.png" alt="事件页的短促声音候选列表"><p>导入片段 → 查找短促声音 → 扫描 → 选候选试听原声上下文 → 确认动作后提参。扫描记录、选区和背景随历史及参数包保存。</p><p>新入口已在限时测试服务验证；当前常驻旧工作台未重启，本页为独立核查记录。</p></section>
<p><a href="report.json">下载本轮核查记录</a></p><script>const p=document.getElementById('player');document.getElementById('clip').onchange=e=>{p.pause();p.src=e.target.value;p.load();};</script></html>'''
    context='../../../../designs/events/'+p['id']+'/'+p['context_run']+'/monitor.wav'
    # This page is served beneath /references/analysis/A_exterior_event_v1/review1/.
    page=page.replace('CONTEXT',context).replace('PROJECT',escape('工作台诊断工程：'+p['name']+'（'+p['id']+'）。无事件参数。'))
    (args.output/'index.html').write_text(page,encoding='utf-8')
    print(json.dumps(dict(result='saved',project_id=p['id'],output=str(args.output)),ensure_ascii=False))


if __name__=='__main__':main()

"""Render diagnostic C colour comparisons and verify a frozen driving bypass."""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True)
args=parser.parse_args()
repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from drive_evidence_v1.sources import read,sha

root=args.workspace/'references/analysis/state_colour_v2'
out=root/'review';out.mkdir(exist_ok=False)
fit=root/'fit_attempt3';profile=fit/'A_rear_rise.colour'
model=repo/'voices/exterior_anchors_v1/A Stationary Upper Mid.model'
index=json.loads((repo/'voices/exterior_anchors_v1/index.json').read_text(encoding='utf-8'))
entry=next(r for r in index['voices'] if r['file']==model.name)
assert sha(model)==entry['model_sha256']
exe=repo/'handoff-build/bin/Release/VslOscColour_probe.exe'
runs=[]
for label,amount in [('base','0'),('half','0.5'),('rise','1'),('transition','rise-fall')]:
    command=[str(exe),str(model),str(profile),str(out/(label+'.wav')),'10',str(entry['base_hz']),amount,'.25','48271']
    result=subprocess.run(command,cwd=repo,check=True,capture_output=True,text=True)
    row=json.loads(result.stdout);audio,rate=sf.read(out/(label+'.wav'),always_2d=True)
    assert rate==48000 and audio.shape==(480000,2) and np.isfinite(audio).all() and row['peak']<.95
    runs.append(dict(name=label,command=command,**row,sha256=sha(out/(label+'.wav'))))
    print(label,row,flush=True)

# Compare the existing driving renderer against an immutable prior binary.
# No state-colour API is called by this host; compare all source buses/controls.
frozen=args.workspace/'baselines/harmonic_body_v1'
manifest=json.loads((frozen/'manifest.json').read_text(encoding='utf-8'))
old=frozen/'bin/VslAtlasDrive_probe.exe'
hashes={r['path']:r['sha256'] for r in manifest['files']}
assert sha(old)==hashes['bin/VslAtlasDrive_probe.exe']
regression=root/'regression';regression.mkdir()
commands=[]
for name,binary in [('frozen',old),('current',repo/'handoff-build/bin/Release/VslAtlasDrive_probe.exe')]:
    voices=repo/'voices/exterior_anchors_v1'
    command=[str(binary),str(voices/index['voices'][0]['file']),str(voices/index['voices'][1]['file']),str(regression/name)]
    for item in index['voices'][2:]:command+=['--anchor',str(voices/item['file'])]
    command+=['--scenario','auto','--seconds','10','--gain','.2','--events','.15','--body-mix','.7']
    result=subprocess.run(command,cwd=repo,check=True,capture_output=True,text=True)
    commands.append(dict(name=name,argv=command,stdout=result.stdout,binary_sha256=sha(binary)))
    print(name,'driving render complete',flush=True)
stems=[]
for path in sorted(regression.glob('frozen_*.wav')):
    suffix=path.name.removeprefix('frozen_');other=regression/('current_'+suffix)
    a,ra=sf.read(path,dtype='float32',always_2d=True);b,rb=sf.read(other,dtype='float32',always_2d=True)
    assert ra==rb==48000 and np.array_equal(a,b),suffix
    stems.append(suffix)
assert len(stems)>=17
assert (regression/'frozen_trace.csv').read_bytes()==(regression/'current_trace.csv').read_bytes()
(regression/'verification.json').write_text(json.dumps(dict(result='pass',stems=stems,trace_equal=True,commands=commands),indent=2)+'\n',encoding='utf-8',newline='\n')

audio,source=read(args.workspace,'A_exterior_revs_extended','exterior_dynamic_observation')
for name,start,stop in [('reference1',232.25,233.45),('reference4',240.60,241.66)]:
    clip=audio[round((start-source['seconds'][0])*48000):round((stop-source['seconds'][0])*48000)].copy()*.25
    fade=240;clip[:fade]*=np.linspace(0,1,fade)[:,None];clip[-fade:]*=np.linspace(1,0,fade)[:,None]
    sf.write(out/(name+'.wav'),clip,48000,subtype='FLOAT')
report=dict(schema='vsl.state-colour-review/1',runs=runs,root_hz=entry['base_hz'],gain=.25,seed=48271,
    model_sha256=sha(model),colour_sha256=sha(profile),binary_sha256=sha(exe),
    fit_sha256=sha(fit/'report.json'),regression_sha256=sha(regression/'verification.json'),
    reference_source=source,human_accepted=False,driver_mapping=False,
    limitation='Automatic swept-clock control failed0.5dB target; up to1.2dB spurious high-band colour. Diagnostic only.')
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')

page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>工况声线诊断 V2</title><style>body{max-width:860px;margin:36px auto;padding:0 20px;font:17px/1.7 system-ui;background:#10151d;color:#e5eaf2}article{background:#1b2431;border-radius:12px;padding:14px 22px;margin:18px 0}h1{font-size:27px}h2{font-size:20px;margin:0}audio{width:100%;margin-top:10px}small{color:#b8c6d9}a{color:#91caff}</style>
<h1>同一音高，工况怎样改变声线</h1><p>先暂停其他发声窗口。比较 0%／50%／100%，再听单次平滑往返，判断这条声线轴是否有用。</p>
<p>这是 A 驻车车外的诊断候选。三次短补油提供起落差异；自动扫频跟踪仍会制造最多约 1.2 dB 高频假变化，尚未接入驾驶，也未替换已认可音色。</p>
<small>同一 OSC 模型、相位、种子、根音 47.391 Hz 和输出增益 0.25；持续生成，无片段循环。拟合时只对共同回落统计做一次期望能量归一，试听没有逐条响度匹配。第128阶及以上保持原增益；此音色轴只在根音45–50 Hz附近有证据。</small>
'''
for title,name,detail in [
    ('0% · 既有驻车 DNA','base','基准本身也尚未通过音色听评。'),
    ('50% · 起落谱形轴','half','只改谐波幅度；左右使用同一增益。'),
    ('100% · 起落谱形轴','rise','完整诊断幅度，不代表满负载或某个踏板位置。'),
    ('单次平滑往返','transition','2秒请求100%，6秒请求0%，120ms跟随；音高始终固定。'),
    ('原录音 · 第一对补油','reference1','原时间232.25–233.45秒，仅端点5ms淡化及统一0.25增益。'),
    ('原录音 · 第四对补油','reference4','原时间240.60–241.66秒；原录音有变调，不能只凭整体亮度判断拟合。')]:
    page+=f'<article><h2>{title}</h2><small>{detail}</small><audio controls preload="none" src="../references/analysis/state_colour_v2/review/{name}.wav"></audio></article>\n'
page+='''<script>document.querySelectorAll('audio').forEach(a=>a.addEventListener('play',()=>document.querySelectorAll('audio').forEach(b=>{if(a!==b)b.pause()})));</script></html>'''
(args.workspace/'research/工况声线诊断V2.html').write_text(page,encoding='utf-8',newline='\n')
print('review/regression complete',len(stems),'identical stems')

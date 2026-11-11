"""Build a common-gain, stopped-by-default listening comparison for first seed."""
import argparse
import json
from pathlib import Path
import shutil
import sys
import urllib.parse
import urllib.request

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True)
parser.add_argument('--root',type=Path,required=True)
args=parser.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from drive_evidence_v1.sources import sha

out=args.root/'review1';out.mkdir(exist_ok=False)
shutil.copy2(__file__,out/'executed_review.py')
temporal=json.loads((args.root/'analysis1/report.json').read_text(encoding='utf-8'))
candidate=json.loads((args.root/'magnitude1/report.json').read_text(encoding='utf-8'))
assert temporal['result']==candidate['result']=='pass'
assert candidate['temporal_report_sha256']==sha(args.root/'analysis1/report.json')
frozen=args.workspace/'baselines/residual_motion_v1'
inputs=[('reference','录音短参考',frozen/'evidence/fit1/reference.wav'),
        ('accepted','原认可 DNA＋低频',frozen/'evidence/fit1/accepted_pair.wav'),
        ('half','新幅度 50%',args.root/'magnitude1/magnitude_78283_0.5.wav'),
        ('full','新幅度 100%',args.root/'magnitude1/magnitude_78283_1.wav')]
records=[]
for name,label,path in inputs:
    if name in ('reference','accepted'):
        relative=path.relative_to(frozen).as_posix()
        assert sha(path)==temporal['frozen_inputs'][relative]
    else:
        trial=next(r for r in candidate['trials'] if r['name']==path.stem)
        assert sha(path)==trial['wav_sha256']
    x,rate=sf.read(path,always_2d=True)
    assert rate==48000 and x.shape[1]==2 and np.isfinite(x).all()
    x*=.5
    fade=np.linspace(0,1,240);x[:240]*=fade[:,None];x[-240:]*=fade[::-1,None]
    assert abs(x).max()<.95
    output=out/(name+'.wav');sf.write(output,x,48000,subtype='PCM_24')
    records.append(dict(name=name,label=label,input=str(path),input_sha256=sha(path),
        output_sha256=sha(output),frames=len(x),peak=float(abs(x).max())))
cards='\n'.join('<section><h2>'+r['label']+'</h2><audio controls preload="metadata" src="../references/analysis/temporal_texture_v1/review1/'+r['name']+'.wav"></audio></section>' for r in records)
html='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>谐波幅度统计 V1</title><style>body{font:16px system-ui;background:#11151a;color:#e6e9ef;max-width:680px;margin:36px auto;padding:0 18px;line-height:1.65}h1{font-size:25px}h2{font-size:17px;margin:0 0 8px}p{color:#bac3cf}section{background:#1b222b;border-radius:12px;padding:16px;margin:14px 0}audio{width:100%}button{font:inherit;padding:8px 16px;border:0;border-radius:7px;cursor:pointer}</style>
<h1>谐波幅度统计 V1</h1><p>请先暂停其他发声窗口。比较高频是否更自然、连贯，以及是否出现颤动或沙感。录音参考较短，后三段均为持续生成的8秒。</p>
<p>共同增益与首尾淡化；没有逐条响度补偿。新候选保留固定相位，改变高频幅度变化，尚未接入驾驶监听。</p>
<button id="stop">全部停止</button>'''+cards+'''
<script>const tracks=[...document.querySelectorAll('audio')];tracks.forEach(a=>a.addEventListener('play',()=>tracks.forEach(b=>{if(a!==b)b.pause()})));document.getElementById('stop').onclick=()=>tracks.forEach(a=>{a.pause();a.currentTime=0});</script></html>'''
page=args.workspace/'research/谐波幅度统计V1.html'
with page.open('x',encoding='utf-8',newline='\n') as stream:stream.write(html)
shutil.copy2(page,out/'review.html')
http=[]
for relative in ['research/谐波幅度统计V1.html',*[f'references/analysis/temporal_texture_v1/review1/{r["name"]}.wav' for r in records]]:
    url='http://127.0.0.1:8789/'+urllib.parse.quote(relative,safe='/')
    try:
        with urllib.request.urlopen(url,timeout=5) as response:
            first=response.read(16);assert response.status==200
            if relative.endswith('.wav'):assert first.startswith(b'RIFF')
            http.append(dict(relative=relative,status=response.status))
    except Exception as exc:
        http.append(dict(relative=relative,error=repr(exc)))
report=dict(schema='vsl.harmonic-magnitude-review/1',result='pass',common_gain=.5,fade_frames=240,
    seed_selection='First predefined procedural seed78283; not selected by listening or best metric',
    files=records,page_sha256=sha(page),page=str(page),http=http,
    source_sha256=sha(__file__),default_stopped=True,human_accepted=False,
    limits=['HTTP and decoded PCM checks only; browser interaction/visual QA not executed',
        'No loudness matching or perceptual acceptance; average band powers may differ',
        'Offline oscillator candidate; no C runtime, driver or model-bank replacement'])
(out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(page=str(page),peak=max(r['peak'] for r in records),http=http),ensure_ascii=False))

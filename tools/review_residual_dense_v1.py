"""Export common-gain density comparisons and verify HTTP bytes/decoding."""
import argparse
import html
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
from urllib.parse import quote,urljoin
from urllib.request import urlopen

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True)
parser.add_argument('--out',type=Path,required=True)
parser.add_argument('--ffmpeg',type=Path,required=True)
parser.add_argument('--server',default='http://127.0.0.1:8789/')
args=parser.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from drive_evidence_v1.sources import sha

root=args.workspace/'references/analysis/residual_dense_v1';run=root/'run1'
plan_path=repo/'research/residual_dense_v1_plan.json';plan=json.loads(plan_path.read_text(encoding='utf-8'))
record=json.loads((run/'report.json').read_text(encoding='utf-8'))
assert record['result']=='technical_pass_only' and not record['human_accepted']
args.out.mkdir(parents=True,exist_ok=False)
paths=[Path(__file__),plan_path,repo/'tools/drive_evidence_v1/sources.py']
for p in paths:
    dest=args.out/'exact_sources'/p.relative_to(repo);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
r=dict(schema='vsl.residual-dense-review/1',result='running',audio=[],
    source_sha256={p.relative_to(repo).as_posix():sha(p) for p in paths},
    input_sha256={str(run/'report.json'):sha(run/'report.json')},browser_interaction_checked=False,human_accepted=False)
try:
    prior=args.workspace/'baselines/line_density_v1';manifest=json.loads((prior/'manifest.json').read_text(encoding='utf-8'))
    accepted=prior/'evidence/render1/raw/accepted.wav'
    expected=next(x['sha256'] for x in manifest['files'] if x['path']=='evidence/render1/raw/accepted.wav')
    assert sha(accepted)==expected
    files=[('accepted','认可基准',accepted)]
    for peak in plan['peaks']:
        row=next(x for x in record['trials'] if x['peak']==peak and x['seed']==plan['review_seed'])
        for key,label in [('mix','完整声音'),('cloud','细节独奏')]:
            path=run/'raw'/f'{key}_{peak}_{plan["review_seed"]}.wav'
            assert sha(path)==row[key+'_sha256']
            files.append((key+'_'+str(peak),label+' · '+str(peak),path))
    audition=args.out/'audition';audition.mkdir()
    start=round(plan['review_start_seconds']*48000);frames=round(plan['review_seconds']*48000)
    fade=np.ones(frames);fade[:240]=np.linspace(0,1,240);fade[-240:]=np.linspace(1,0,240)
    for key,label,path in files:
        r['input_sha256'][str(path)]=sha(path)
        source,rate=sf.read(path,always_2d=True);assert rate==48000
        clip=source[start:start+frames]*plan['review_gain']*fade[:,None]
        assert clip.shape==(frames,2) and np.isfinite(clip).all() and abs(clip).max()<plan['tolerances']['review_peak_maximum']
        out=audition/(key+'.wav');sf.write(out,clip,48000,subtype='PCM_24')
        decoded,rate=sf.read(out,always_2d=True);assert rate==48000 and abs(decoded-clip).max()<2**-23
        result=subprocess.run([str(args.ffmpeg),'-v','error','-i',str(out),'-f','null','-'],capture_output=True,text=True,timeout=30)
        assert result.returncode==0,result.stderr
        r['audio'].append(dict(name=key,label=label,frames=frames,peak=float(abs(clip).max()),rms=float(np.sqrt(np.mean(clip**2))),
            sha256=sha(out),FFmpeg_decodes=True,decoded_max_error=float(abs(decoded-clip).max())))
    def card(key,label):
        relative='../references/analysis/residual_dense_v1/'+args.out.name+'/audition/'+key+'.wav'
        return '<div class="card"><label>'+html.escape(label)+'</label><audio controls preload="metadata" src="'+relative+'"></audio></div>'
    body='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
    body+='<title>载波密度对照 V1</title><style>body{font:16px/1.6 system-ui;max-width:840px;margin:32px auto;padding:0 20px;background:#f4f5f5;color:#20272b}h1{font-size:25px}h2{font-size:19px}.card{background:white;border:1px solid #dce1e3;border-radius:8px;padding:12px 16px;margin:10px 0}label{display:block;margin-bottom:8px}audio{width:100%;height:42px}details{margin-top:28px;font-size:14px}</style>'
    body+='<h1>载波密度对照 V1</h1><p>先暂停其他发声窗口。比较持续排气的电子感、沙感和有无持续颤动。</p><p>所有候选保留相同DNA与低频，使用共同增益；每段8秒，没有逐版响度补偿。</p>'
    body+='<h2>完整声音</h2>'+card('accepted','认可基准')
    labels={32:'原密度 · 32',64:'稍密 · 64',128:'较密 · 128',256:'最密 · 256'}
    for peak in plan['peaks']:body+=card('mix_'+str(peak),labels[peak])
    body+='<h2>细节层独奏</h2>'
    for peak in plan['peaks']:body+=card('cloud_'+str(peak),labels[peak])
    body+='<details><summary>实验范围</summary><p>数字表示6–8kHz频带的共享载波数；其他频带按带宽分配。32／64／128／256分别分配512／590／912／1746条共享与独立振荡器。候选沿用上一轮50%高频谐波工程分配，不代表测得的噪声比例。32与上一轮同档声音一致。</p><p>全为持续OSC生成，离线汇总，固定音高、单一A移动尾排情境。近双mono录音不能证明立体声宽度。增加密度改变拍频，不保证自然度；候选未接驾驶默认，尚未获听评认可。</p></details>'
    body+='<script>document.querySelectorAll("audio").forEach(a=>a.addEventListener("play",()=>document.querySelectorAll("audio").forEach(b=>{if(a!==b)b.pause()})))</script></html>'
    page=args.workspace/'research/载波密度对照V1.html';assert not page.exists()
    page.write_text(body,encoding='utf-8',newline='\n');shutil.copy2(page,args.out/'page.html')
    url=quote(urljoin(args.server,'research/载波密度对照V1.html'),safe=':/')
    with urlopen(url,timeout=15) as response:assert response.status==200 and response.read()==page.read_bytes()
    sources=re.findall(r'<audio[^>]*src="([^"]+)"',body);assert len(sources)==len(set(sources))==9
    for relative in sources:
        with urlopen(urljoin(url,relative),timeout=15) as response:
            assert response.status==200 and response.read()==(audition/Path(relative).name).read_bytes()
    r.update(result='pass',url=url,page_sha256=sha(page),HTTP_page_bytes_exact=True,HTTP_audio_bytes_exact=True,
        review_gain=plan['review_gain'],per_file_gain_normalization=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:(args.out/'report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(result=r['result'],audio=len(r['audio']),maximum_peak=max(x['peak'] for x in r['audio']))))

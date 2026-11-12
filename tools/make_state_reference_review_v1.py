"""Approved non-driving/state references plus fresh current-system captures."""
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

cases=[('start','启动／接火','A_start_context',(33,40),'车内启动语境；接火时刻、RPM未精确标定。'),
    ('low','驻车低转','A_exterior_low_rev',(208,211),'车外低转参考；不能确认是850RPM暖怠速。'),
    ('blips','驻车补油','A_exterior_blips',(238,248),'驻车尾排升降转；挡位、踏板与负载未被测定。'),
    ('bay','机舱混合声','A_engine_bay_context',(270,277),'含发动机／进排气／空间，不能当作独立进气或机械录音。'),
    ('release','车内减速','E_corsa_first_context',(52,54.4),'已有3挡减速画面观察；喷油、踏板及准确同步未知。'),
    ('shifts','车内升挡语境','E_corsa_second_context',(82,94),'已有1→6挡画面观察；显示时刻不能当作切扭／离合时刻。')]
args.out.mkdir(parents=True,exist_ok=False);(args.out/'audio').mkdir()
sources=[Path(__file__),repo/'tools/drive_evidence_v1/sources.py']
for path in sources:
    target=args.out/'exact_sources'/path.relative_to(repo);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
catalog_path=args.workspace/'references/segments_v1.json';catalog=json.loads(catalog_path.read_text(encoding='utf-8'))
shutil.copy2(catalog_path,args.out/'segments_v1.json')
device=args.workspace/'references/analysis/system_status_v1/device1'
status=json.loads((device/'report.json').read_text(encoding='utf-8'));assert status['result']=='short_device_checks_passed'
audio_by_key={}
r=dict(schema='vsl.state-reference-review/1',result='running',clips=[],input_sha256={str(catalog_path):sha(catalog_path),str(device/'report.json'):sha(device/'report.json')},
    source_sha256={p.relative_to(repo).as_posix():sha(p) for p in sources},browser_interaction_checked=False,human_timbre_accepted=False)
try:
    checked=set()
    for key,title,segment_id,seconds,limit in cases:
        segment=catalog['segments'][segment_id];source=catalog['sources'][segment['source']]
        assert segment['seconds'][0]<=seconds[0]<seconds[1]<=segment['seconds'][1]
        if segment['source'] not in checked:
            for part in ('raw','master'):
                path=args.workspace/source[part];assert sha(path)==source[part+'_sha256'];r['input_sha256'][str(path)]=sha(path)
            checked.add(segment['source'])
        with sf.SoundFile(args.workspace/source['master']) as stream:
            assert stream.samplerate==48000 and stream.channels==2
            first,last=[round(t*48000) for t in seconds];stream.seek(first);audio=stream.read(last-first,always_2d=True)
        audio_by_key[key]=audio
        r['clips'].append(dict(key=key,title=title,source=segment['source'],segment=segment_id,seconds=list(seconds),
            limits=limit,kind='approved_recording_reference'))
    for name,title in [('bench','当前C：点火／台架转速变化'),('pedals','当前C：起步／换挡／收油／制动／停火')]:
        path=device/'device'/(name+'.wav');audio,rate=sf.read(path,always_2d=True);assert rate==48000
        r['input_sha256'][str(path)]=sha(path)
        audio_by_key['system_'+name]=audio
        r['clips'].append(dict(key='system_'+name,title=title,kind='current_C_device_capture',
            limits='来自刚完成的静音设备检查，含测试控制与空间切换；不是上方实录同一动作的复刻，也未获音色听评。'))
    for clip in r['clips']:
        audio=audio_by_key[clip['key']];fade=np.ones(len(audio));fade[:240]=np.linspace(0,1,240);fade[-240:]=np.linspace(1,0,240)
        rendered=audio*.5*fade[:,None];assert np.isfinite(rendered).all() and abs(rendered).max()<.95
        path=args.out/'audio'/(clip['key']+'.wav');sf.write(path,rendered,48000,subtype='PCM_24')
        done=subprocess.run([str(args.ffmpeg),'-v','error','-i',str(path),'-f','null','-'],capture_output=True,text=True,timeout=30)
        assert done.returncode==0,done.stderr
        clip.update(frames=len(rendered),peak=float(abs(rendered).max()),sha256=sha(path),FFmpeg_decodes=True)
    prefix='../references/analysis/system_status_v1/'+args.out.name+'/audio/'
    body='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>状态素材与系统回放 V1</title>'
    body+='<style>body{font:16px/1.6 system-ui;max-width:860px;margin:30px auto;padding:0 20px;background:#f4f5f5;color:#20272b}h1{font-size:25px}h2{font-size:20px}.card{background:white;border:1px solid #dce1e3;border-radius:8px;padding:12px 16px;margin:12px 0}audio{width:100%;height:42px}p.note{font-size:14px;color:#52616b}strong{font-weight:650}</style>'
    body+='<h1>状态素材与系统回放 V1</h1><p>先暂停其他发声窗口。这里汇总现有真实参考与当前C系统检查录音，方便查看覆盖范围。</p><p><strong>系统已能运行；其余状态的实录拟合和逐项同步对照尚未完成。</strong>录音视角、动作与音量不同，下面不是音色优劣A/B测试。</p>'
    for kind,title in [('approved_recording_reference','已批准的真实素材'),('current_C_device_capture','当前C系统的状态回放')]:
        body+='<h2>'+title+'</h2>'
        for clip in r['clips']:
            if clip['kind']!=kind:continue
            label=clip['title']
            if 'source' in clip:label+=' · '+clip['source']+' '+str(clip['seconds'][0])+'–'+str(clip['seconds'][1])+'s'
            body+='<div class="card"><strong>'+html.escape(label)+'</strong><p class="note">'+html.escape(clip['limits'])+'</p><audio controls preload="metadata" src="'+prefix+clip['key']+'.wav"></audio></div>'
    body+='<p class="note">参考均来自已批准的A／E，按原时间切取；试听仅共同0.5增益和5ms首尾淡化，没有降噪、EQ、压缩或逐条响度匹配。熄火／独立回火／独立进气暂无已确认的干净参考。静音设备检查不代表已通过人耳听评；12通道目前只有离线验证。</p>'
    body+='<script>document.querySelectorAll("audio").forEach(a=>a.addEventListener("play",()=>document.querySelectorAll("audio").forEach(b=>{if(a!==b)b.pause()})))</script></html>'
    page=args.workspace/'research/状态素材与系统回放V1.html';assert not page.exists();page.write_text(body,encoding='utf-8',newline='\n')
    shutil.copy2(page,args.out/'page.html');url=quote(urljoin(args.server,'research/状态素材与系统回放V1.html'),safe=':/')
    with urlopen(url,timeout=15) as response:assert response.status==200 and response.read()==page.read_bytes()
    for relative in re.findall(r'<audio[^>]*src="([^"]+)"',body):
        with urlopen(urljoin(url,relative),timeout=15) as response:
            assert response.status==200 and response.read()==(args.out/'audio'/Path(relative).name).read_bytes()
    r.update(result='pass',url=url,page_sha256=sha(page),HTTP_bytes_verified=True,
        meaning='Reference inventory and functional-system captures, not a matched-state listening comparison or acceptance')
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:(args.out/'report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(result=r['result'],clips=len(r['clips']),url=r['url'])))

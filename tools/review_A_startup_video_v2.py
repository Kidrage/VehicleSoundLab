"""Publish approved same-A action context, indicated bounds and explicit gaps."""
import argparse,html,json,shutil,subprocess,sys,urllib.request
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
from drive_evidence_v1.sources import sha
a.out.mkdir(parents=True,exist_ok=False)
root=a.workspace/'references/analysis/A_startup_video_v2'
observation=json.loads((root/'observation1/report.json').read_text(encoding='utf-8'))
analysis=json.loads((root/'analysis1/report.json').read_text(encoding='utf-8'))
assert analysis['result']=='indicated_shape_observed_and_coarse_family_tested'
assert not analysis['paired_coarse_gate']['passed']
video=Path(observation['source']);master=a.workspace/analysis['approved_audio']['master']
assert sha(video)==observation['source_sha256'] and sha(master)==analysis['approved_audio']['master_sha256']
command=['ffmpeg','-v','info','-nostdin','-n','-to','39.8','-i',str(video),'-to','39.8','-i',str(master),
    '-filter_complex','[0:v]trim=start=35.5:end=39.8,setpts=PTS-STARTPTS[v];[1:a]atrim=start=35.5:end=39.8,asetpts=PTS-STARTPTS[a]',
    '-map','[v]','-map','[a]','-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p',
    '-c:a','aac','-b:a','192k','-movflags','+faststart','-shortest',str(a.out/'A_start_context.mp4')]
done=subprocess.run(command,capture_output=True,timeout=90)
(a.out/'encode.log').write_bytes(done.stderr);assert done.returncode==0
shutil.copy2(root/'analysis1/comparison.png',a.out/'comparison.png')
rows={v['source_frame_index']:v for v in observation['decoded_frames']}
cards=[]
for index,label in [(2244,'37.437s：仪表仍接近零'),(2280,'38.038s：冲转高点附近'),(2334,'38.939s：回落后低转')]:
    row=rows[index];source=root/'observation1'/row['file'];target=a.out/row['file'];shutil.copy2(source,target)
    assert sha(source)==row['sha256'];cards.append((label,target.name))
body=['<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width">',
    '<title>A启动动作与仪表 · V2</title><style>body{font:16px system-ui;max-width:980px;margin:32px auto;padding:0 20px;background:#f6f7f8}section{background:white;padding:20px;margin:18px 0;border-radius:12px}video,img{max-width:100%}p{line-height:1.7}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px}figure{margin:0}</style>',
    '<h1>A：启动动作与仪表</h1><p>目标是驻车启动后的冲转与回落。画面显示P挡、车速0；踏板与负载未建立。新高清局部材料来自已批准的同一A视频，整片下载曾超时，本页只使用已成功解码的片段。</p>',
    '<section><video controls preload="metadata" src="A_start_context.mp4"></video><p>源画面／音轨35.5–39.8秒，各按自身来源秒数裁切后合并；没有估计或校正显示／音频迟延。这是动作参考，不是精确AV同步或ECU遥测。视频重编码，音轨AAC192k，无去噪、增益或声纹合成。</p></section>',
    '<section><h2>可读出的目标范围</h2><p>20个原生帧粗读数显示：指针从接近零升至约1800–2500RPM的冲转高点，再回到约650–1150RPM的低转区间。区间为视觉估计，包含针宽与透视读数限制；不是置信区间或瞬时真实曲轴转速。仪表启动图形变化不能当作接火瞬间。</p>',
    '<p>旧C演示模拟的是两次启动／熄火，工程峰值1150RPM。该峰值低于本次指示高点的下界，未对齐A动作；850RPM回落值落在本次低转粗读范围内。当前没有修改控制器或音色。</p><div class="cards">']
for label,name in cards:body.append(f'<figure><img src="{name}" alt="原生仪表裁切"><figcaption>{html.escape(label)}</figcaption></figure>')
body+=['</div></section><section><h2>声音仍缺哪一步</h2><p>以新仪表范围限定的85Hz根音假设做一次固定条件复核，3／5两组声学参考都未找到完整相连轨迹。没有扩大搜索直到通过，也没有生成新启动DNA。已知扫频控制通过仅能说明算法在已知输入上工作，不能代替实录资格。</p>',
    '<p>下一步应分开起动机、接火冲转、回落／低转的声学坐标和时变谱形。先得到动作与频率关系，再接入同一驾驶状态机；不能把一档低转DNA拉高就宣布还原整个启动。</p><img src="comparison.png" alt="仪表区间、原录音频谱与失败的粗周期轨迹"></section></html>']
(a.out/'index.html').write_text('\n'.join(body),encoding='utf-8',newline='\n')
files=[]
for path in sorted(a.out.iterdir()):
    if path.suffix not in ('.mp4','.png','.html'):continue
    url='http://127.0.0.1:8789/'+path.relative_to(a.workspace).as_posix()
    with urllib.request.urlopen(url,timeout=10) as response:assert response.read()==path.read_bytes()
    if path.suffix=='.mp4':
        decoded=subprocess.run(['ffmpeg','-v','error','-i',str(path),'-f','null','-'],capture_output=True,timeout=30)
        assert decoded.returncode==0
    files.append(dict(file=path.name,sha256=sha(path),url=url))
r=dict(result='approved_A_context_and_observation_page_published',media_command=command,
    nominal_source_interval_seconds=[35.5,39.8],independent_AV_alignment_established=False,
    gain_or_denoising=False,files=files,source_sha256=sha(__file__))
(a.out/'report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(result=r['result'],page='http://127.0.0.1:8789/'+(a.out/'index.html').relative_to(a.workspace).as_posix())))

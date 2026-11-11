"""Generate the editable SVG architecture plate; no Python packages required."""
from html import escape
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "系统总图.svg"
parts = ['''<svg xmlns="http://www.w3.org/2000/svg" width="1320" height="984" viewBox="0 0 1320 984" role="img" aria-labelledby="title desc">
<title id="title">Vehicle Sound Lab 系统总图</title>
<desc id="desc">上半部分是现有 C 驾驶声场与录制回放，下半部分是独立声纹研究与后续接入条件。</desc>
<style>
text{font-family:"Microsoft YaHei UI","Microsoft YaHei","Noto Sans CJK SC",sans-serif;fill:#132e41}
.eyebrow{font-size:14px;letter-spacing:2px;font-weight:bold;fill:#326675}.title{font-size:40px;font-weight:bold}
.sub{font-size:17px;fill:#405a68}.band{font-size:22px;font-weight:bold}.tag{font-size:14px;font-weight:bold;fill:#326675}
.label{font-size:20px;font-weight:bold}.copy{font-size:15px;fill:#294453}.file{font-size:14px;fill:#3a5867}
</style>
<defs>
<marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto" markerUnits="userSpaceOnUse"><path d="M0 0L8 4L0 8z" fill="#3c6675"/></marker>
<marker id="trace" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto" markerUnits="userSpaceOnUse"><path d="M0 0L8 4L0 8z" fill="#685e88"/></marker>
</defs>''']


def rect(x,y,w,h,fill,stroke="none",r=12):
    parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}" stroke="{stroke}"/>')


def text(x,y,s,cls):
    parts.append(f'<text x="{x}" y="{y}" class="{cls}">{escape(s)}</text>')


def edge(d,kind="live",arrow=True):
    color = "#3c6675" if kind=="live" else "#685e88"
    dash = ' stroke-dasharray="7 5"' if kind!="live" else ""
    end = (' marker-end="url(#arrow)"' if kind=="live" else ' marker-end="url(#trace)"') if arrow else ""
    parts.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="2" stroke-linejoin="round"{dash}{end}/>')


def card(x,y,w,h,title,lines,fill="#ffffff",stroke="#b5cbd2"):
    rect(x,y,w,h,fill,stroke)
    text(x+17,y+29,title,"label")
    for i,line in enumerate(lines):
        text(x+17,y+54+21*i,line,"file" if i==0 else "copy")


rect(0,0,1320,984,"#f4f7f8",r=0)
text(44,33,"VSL  /  ENGINEERING HANDOFF  /  2026.11.11","eyebrow")
text(44,79,"Vehicle Sound Lab · 系统总图","title")
text(46,110,"统一入口：Launch-System.cmd   ｜   C11 驾驶与原生监听   ｜   分层声源、空间输出与可重建驾驶录制","sub")

rect(32,131,1256,502,"#e9f2f5","#cadce2",18)
text(56,169,"01  驾驶主线","band")
text(237,168,"DSP / APP 0.20.0  ·  驾驶与录制功能可用，目标音色仍在研究","tag")

# Control path, then fork into three sources. Branches are drawn behind cards.
edge("M396 233H459")
edge("M799 233H862")
edge("M1032 274V295H226V316")
edge("M629 295V316")
edge("M1032 295V316")
for x in (226,629,1032):
    edge(f"M{x} 410V431H226",arrow=False)
edge("M226 431V450")
edge("M396 496H459")
edge("M799 496H862")
# The record/replay edge bypasses the vehicle UI and goes back into the same control path.
edge("M178 274V290H46V588H56","trace")
edge("M629 563V547H425V233H459","trace")

card(56,192,340,82,"控制入口",["src/app/ · UI、键盘、预设","控制快照 VslParams"])
card(459,192,340,82,"驾驶状态机 · 200 Hz",["src/drive/ · VslDrive","启停、换挡、断油、RPM 与负载"])
card(862,192,340,82,"声层映射与时钟",["orchestrator.c / clocks.c / voicing.c","状态包络、独立转动与音色时钟"])

card(56,316,340,94,"DNA / 排气",["dna.c / high_orders.c","旧 .dna 与排气阶次；默认 Original OSC"])
card(459,316,340,94,"机体轰鸣",["pad.c / acoustics.c","现有 PAD；IR 返回进入 BODY"])
card(862,316,340,94,"噪声 / NVH / 事件",["nvh.c / mechanical*.c / events.c","机械、进气、空气、路、风与瞬态"])

card(56,450,340,93,"10 路独立声源",["engine.c → VslObjectFrame","空间处理前、主音量前；可独立导出"])
card(459,450,340,93,"空间与输出混音",["src/spatial/ · scene.c / propagation.c","布局、可选几何传播、主音量"])
card(862,450,340,93,"监听与导出",["audio_device.c / src/cli/","实时 stereo；离线 stereo / 7.1.4"])

card(56,563,340,62,"已应用控制帧 → Take",["src/session/ / src/io/take_file.c"],"#f5f2fa","#c6b9da")
card(459,563,743,62,"Take 重放 → 同一 C 引擎",["take_render.c · 恢复参数、DNA/IR、seed；重新合成，不是播放旧 WAV"],"#f5f2fa","#c6b9da")
edge("M396 588H459","trace")

rect(32,654,1256,282,"#edf2ec","#d1dfd0",18)
text(56,690,"02  独立音色研究","band")
text(271,689,"分析在离线进行  ·  监听实时生成  ·  研究模型未替换驾驶声源","tag")
edge("M356 779H391")
edge("M691 779H726")
card(56,719,300,119,"批准素材与观察",["references/segments_v1.json","A 车外 / B 车内 / D 台架 / E 车内","切片、身份、限制与验证分别建档"],"#fff","#b7ccbb")
card(391,719,300,119,"离线分析 / 生成模型",["tools/ · Python 与音频分析脚本","声线、幅度 / 相位和统计变化","模型预载；音频线程不读素材"],"#fff","#b7ccbb")
card(726,710,476,82,"Sound DNA V1 · 固定相位方案获认可",["modules/sound_dna/ → sustain_monitor_v3","独立持续 OSC；V10 监听 + 两个合成复用测试"],"#fff","#b7ccbb")
edge("M708 779V840H726")
card(726,800,476,82,"低频轰鸣 V2 · 听评未通过",["modules/low_rumble/ → sustain_monitor_v4","风声／低频噪声感；保留对照与四种录音视角"],"#fff7ec","#d4b490")
text(56,912,"下一步（未接入驾驶）：提取发动机同步低频 → 留出验证相位和包络 → 等低频 RMS 听评 → 新版本适配工况。","sub")
text(44,964,"实线：当前处理路径     虚线：Take 录制与重放     入口职责、接口、文件哈希及历史阶段见交接索引。","file")
parts.append("</svg>")
OUT.write_text("\n".join(parts)+"\n",encoding="utf-8")


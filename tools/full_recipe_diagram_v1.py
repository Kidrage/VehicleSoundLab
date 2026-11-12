"""Draw matching SVG/PNG of the current C atlas driving chain."""
from html import escape
from pathlib import Path
def draw(directory):
    from PIL import Image,ImageDraw,ImageFont
    directory=Path(directory);width,height=1440,1120
    image=Image.new('RGB',(width,height),'#f4f7f8');pen=ImageDraw.Draw(image)
    font_path='C:/Windows/Fonts/msyh.ttc';fonts={n:ImageFont.truetype(font_path,n) for n in (16,18,22,28,36)}
    svg=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
         '<title>Vehicle Sound Lab 当前统一 C 系统</title>',
         '<desc>唯一驾驶控制器、Sound DNA、独立低频与连续细节、空间路由、自包含行程。怠速及带载音色仍待标定。</desc>',
         '<rect width="1440" height="1120" fill="#f4f7f8"/>']
    def text(x,y,value,size=18,colour='#193347'):
        pen.text((x,y),value,font=fonts[size],fill=colour,anchor='lt')
        svg.append(f'<text x="{x}" y="{y}" dominant-baseline="text-before-edge" font-family="Microsoft YaHei UI,Microsoft YaHei,sans-serif" font-size="{size}" fill="{colour}">{escape(value)}</text>')
    def box(x,y,w,h,heading,lines,fill='#ffffff'):
        pen.rounded_rectangle((x,y,x+w,y+h),radius=14,fill=fill,outline='#bfd0d8',width=2)
        svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" fill="{fill}" stroke="#bfd0d8" stroke-width="2"/>')
        text(x+18,y+15,heading,22)
        for i,line in enumerate(lines):text(x+18,y+53+28*i,line,16)
    def arrow(points):
        pen.line(points,fill='#587789',width=3)
        x,y=points[-1];px,py=points[-2]
        tri=[(x,y),(x-10,y-6),(x-10,y+6)] if x>px else [(x,y),(x-6,y-10),(x+6,y-10)]
        pen.polygon(tri,fill='#587789')
        svg.append('<polyline points="'+' '.join(f'{x},{y}' for x,y in points)+'" fill="none" stroke="#587789" stroke-width="3"/>')
        svg.append('<polygon points="'+' '.join(f'{x},{y}' for x,y in tri)+'" fill="#587789"/>')
    text(44,24,'VSL  /  C11 ENGINEERING HANDOFF  /  2026.11.13',16,'#3c6878')
    text(44,61,'Vehicle Sound Lab · 当前统一系统',36)
    text(44,118,'新 atlas 驾驶链 · 540份 C/H · 55项 CTest · 独立声源参数与设备／文件操作',18)
    box(44,176,420,142,'驾驶输入与原生监听',['点火 / 油门 / 制动 / 挡位 / 转速台架','experiments/atlas_monitor_v1','开始、停止、分层量与行程录放'])
    box(510,176,420,142,'唯一驾驶控制器 · 200 Hz',['src/drive + core/orchestrator','RPM / 负载 / 启停 / 换挡 / 断油','各层包络由状态统一调度'])
    box(976,176,420,142,'素材 → 纯参数',['批准素材 → 离线分析 / 留出核查','车型、录音视角、状态各自保留','.model / .rdetail / .sres；无PCM循环'])
    arrow([(464,247),(510,247)])
    arrow([(720,318),(720,345),(254,345),(254,372)])
    arrow([(720,318),(720,372)])
    arrow([(1186,318),(1186,372)])
    box(44,372,420,176,'Sound DNA · 主声线',['sound_dna + dna_atlas','一组 OSC / 固定平均相位 / 统计幅度','按声学根音插值；共享实际相位','35%配方：主DNA替换量随细节淡出'])
    box(510,372,420,176,'低频 · 两条独立路径',['harmonic_body：主DNA互补分层','drive_recipe：实测相位LF独立参数','共用主DNA相位；独立量与机体包络','不能把互补分层当作新增低频声源'])
    box(976,372,420,176,'连续细节与辅助层',['drive_resonance → Rdt / Rvs','AR／双通道VAR / SOS / 连续新激励','drive_aux / start_texture / events','进气、机械、启动、换挡等分开维护'])
    for x in (254,720,1186):arrow([(x,548),(x,579)])
    box(44,579,1352,126,'统一调度与分轨 · modules/atlas_drive',['可选 recipe_bank：先计算DNA功率替换 → 主DNA采样 → 同相位LF与细节 → 各自包络 → 一次混音',
        '独立采集主DNA、互补低频、相干LF、连续细节、辅助与事件；静音／范围外继续推进内部状态'],'#e7f1f5')
    arrow([(254,705),(254,745)])
    arrow([(720,705),(720,745)])
    arrow([(1186,705),(1186,745)])
    box(44,745,420,144,'空间与输出',['stereo_bed / src/spatial','观察L/R保留；辅助对象只空间化一次','设备stereo；2 / 12通道离线导出'])
    box(510,745,420,144,'录制 → 自包含重合成',['atlas_take / atlas_take_io','schema8 / 29控制字段 / 模型与seed','严格版本身份；保存分层源与输出哈希'])
    box(976,745,420,144,'宿主与实时边界',['atlas_monitor / win_output','预分配缓冲、启停淡变、成功提交帧','加载 / 校验 / 文件IO均在音频线程外'])
    box(44,925,1352,150,'本轮接入与未完成项',['入口：Launch-Full-Recipe-Drive-Study.cmd；默认停止、未点火、房间0；保留35%原参数',
        '此配方仅有46.875 Hz局部锚点；1/120是工程映射。支持区不是实测发动机RPM／负载覆盖。',
        '真实怠速、中低转带载、同RPM负载声纹、多发动机听评及实际7.1.4验证仍待完成。'],'#fff3e5')
    svg.append('</svg>');(directory/'系统总图.svg').write_text('\n'.join(svg)+'\n',encoding='utf-8')
    image.save(directory/'系统总图.png')
if __name__=='__main__':draw(Path(__file__).resolve().parents[1]/'handoff')

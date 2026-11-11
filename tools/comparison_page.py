"""Reusable local comparison player. Caller supplies copy, sources and labels."""
import html
import json


def comparison_page(*,title,version,headline,intro,cases,methods,extra,footer):
    esc=html.escape
    options=''.join(f'<option value="{esc(key)}">{esc(item["label"])}</option>' for key,item in cases.items())
    buttons=''.join(f'<button data-method="{esc(key)}" aria-pressed="false">{esc(name)}</button>' for key,name in methods.items())
    template='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__</title><style>
*{box-sizing:border-box}body{margin:0;background:#111a22;color:#dfeaf0;font:16px/1.7 system-ui,sans-serif}main{max-width:900px;margin:40px auto;padding:0 24px 60px}h1{font-size:29px;line-height:1.4;margin:8px 0 20px}h2{font-size:19px}.tag{color:#88d8c0;font-size:13px;letter-spacing:1px}section{margin:24px 0;padding:26px;border:1px solid #31434f;border-radius:14px;background:#192733}.quiet{font-size:14px;color:#a0b6c2}select{width:100%;font:inherit;color:#e3eff3;background:#111d27;border:1px solid #4b6574;border-radius:7px;padding:11px}label{font-size:14px;display:block;margin-bottom:8px;color:#bed0d9}.buttons{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:18px 0}button{font:inherit;padding:12px;background:#233745;color:#deebee;border:1px solid #496674;border-radius:8px;cursor:pointer}button[aria-pressed=true]{background:#a7e7d2;color:#092b24;border-color:#a7e7d2}button:focus-visible,select:focus-visible{outline:3px solid #a7e7d2;outline-offset:3px}#now{color:#a7e7d2;min-height:28px}audio{display:block;width:100%;margin:16px 0}p{margin:10px 0}a{color:#8ad9c5}img{width:100%;border-radius:8px}details{margin:22px 0}summary{cursor:pointer;color:#b0cbd8}@media(max-width:550px){main{padding:0 16px 40px;margin-top:26px}section{padding:18px}h1{font-size:25px}}
</style><main><div class="tag">VEHICLE SOUND LAB · __VERSION__</div><h1>__HEADLINE__</h1>__INTRO__
<section><h2>相同驾驶输入，比较声音响应</h2><label for="case">场景</label><select id="case">__OPTIONS__</select><div class="buttons" role="group" aria-label="比较版本">__BUTTONS__</div><div id="now" role="status" aria-live="polite"></div><audio id="player" controls preload="metadata"></audio><p id="gain" class="quiet"></p></section>__EXTRA__<footer>__FOOTER__</footer></main>
<script>const data=__DATA__,names=__NAMES__;
const audio=document.getElementById('player'),selector=document.getElementById('case'),status=document.getElementById('now');let method=Object.keys(names).at(-1),serial=0;
function load(preserve){const token=++serial,position=preserve?audio.currentTime:0,playing=preserve&&!audio.paused;audio.pause();audio.src=data[selector.value].takes[method];status.textContent=data[selector.value].label+' · '+names[method];document.getElementById('gain').textContent=data[selector.value].gain_note;audio.onloadedmetadata=()=>{if(token!==serial)return;audio.currentTime=Math.min(position,Math.max(0,audio.duration-.02));if(playing)audio.play().catch(()=>{});};for(const b of document.querySelectorAll('[data-method]'))b.setAttribute('aria-pressed',b.dataset.method===method?'true':'false');audio.load();}
selector.addEventListener('change',()=>load(false));for(const b of document.querySelectorAll('[data-method]'))b.addEventListener('click',()=>{method=b.dataset.method;load(true);});load(false);for(const p of document.querySelectorAll('audio'))p.addEventListener('play',()=>{for(const other of document.querySelectorAll('audio'))if(other!==p)other.pause();});
</script></html>'''
    values=dict(TITLE=esc(title),VERSION=esc(version),HEADLINE=esc(headline),INTRO=intro,
        OPTIONS=options,BUTTONS=buttons,EXTRA=extra,FOOTER=footer,
        DATA=json.dumps(cases,ensure_ascii=False).replace('</','<\\/'),NAMES=json.dumps(methods,ensure_ascii=False))
    for key,value in values.items():template=template.replace('__'+key+'__',value)
    return template

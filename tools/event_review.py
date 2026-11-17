"""Small shared one-player page for fixed-gain synthesis research comparisons."""
import html
import json


def page(title,paragraphs,tracks,links,plot='curves.png'):
    buttons=''.join(f'<button data-track="{i}">{html.escape(row["label"])}</button>' for i,row in enumerate(tracks))
    prose=''.join('<p>'+html.escape(text)+'</p>' for text in paragraphs)
    downloads=' · '.join(f'<a href="{html.escape(path,quote=True)}" download>{html.escape(label)}</a>' for path,label in links)
    template='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>TITLE</title>
<style>body{max-width:980px;margin:32px auto;padding:0 20px;background:#111815;color:#e3ebe2;font:16px/1.65 system-ui}h1{font-size:25px}button{color:inherit;background:#26342b;border:1px solid #718469;padding:12px;margin:5px;cursor:pointer}button[aria-pressed=true]{background:#425e36}audio,img{width:100%}a{color:#bddea6}.tracks{display:flex;flex-wrap:wrap}#status{min-height:54px}</style>
<h1>TITLE</h1>PROSE<div class="tracks">BUTTONS</div><p id="status">选择声音后播放</p><audio id="player" controls preload="none"></audio><p><a id="download" download>下载当前试听</a></p><p>DOWNLOADS</p><img src="PLOT" alt="原素材与新旧C的高频能量起伏对照"><script>
const tracks=ROWS,player=document.querySelector('#player');let currentURL=null,request=0;
document.querySelectorAll('[data-track]').forEach(b=>b.onclick=async()=>{const ticket=++request,row=tracks[Number(b.dataset.track)],running=!player.paused,time=player.currentTime;player.pause();document.querySelector('#status').textContent='载入中…';try{const response=await fetch(row.file);if(!response.ok)throw Error(response.status);const blob=await response.blob();if(ticket!==request)return;const url=URL.createObjectURL(blob);if(currentURL)URL.revokeObjectURL(currentURL);currentURL=url;player.src=url;player.onloadedmetadata=()=>{if(ticket!==request)return;player.currentTime=Math.min(time,Math.max(0,player.duration-.02));if(running)player.play();};document.querySelector('#status').textContent=row.label+' · '+row.description;const a=document.querySelector('#download');a.href=row.file;a.download=row.file;document.querySelectorAll('[data-track]').forEach(x=>x.setAttribute('aria-pressed',String(x===b)));}catch(e){document.querySelector('#status').textContent=String(e);}});
window.addEventListener('pagehide',()=>{if(currentURL)URL.revokeObjectURL(currentURL);});
</script></html>'''
    for key,value in [('TITLE',html.escape(title)),('PROSE',prose),('BUTTONS',buttons),('DOWNLOADS',downloads),
                      ('PLOT',html.escape(plot,quote=True)),('ROWS',json.dumps(tracks,ensure_ascii=False).replace('</','<\\/'))]:
        template=template.replace(key,value)
    return template

"""Small reusable single-player page; source generation stays outside the UI."""
import html,json

def make_page(title,intro,notes,versions,bands,durations,files,default_version):
    def options(items,selected):
        return ''.join('<option value="'+html.escape(k,quote=True)+'"'+(' selected' if k==selected else '')+'>'+html.escape(v)+'</option>' for k,v in items.items())
    page='''<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>__TITLE__</title><style>*{box-sizing:border-box}body{font:16px system-ui,sans-serif;max-width:760px;margin:40px auto;padding:0 20px;background:#f3f5f6;color:#18232b}main{background:white;border-radius:14px;padding:28px}h1{font-size:25px;margin:0 0 14px}p{line-height:1.7;color:#46545d}label{display:block;margin:20px 0 7px}select{font:inherit;width:100%;padding:10px;border:1px solid #b9c4ca;border-radius:7px;background:white}audio{width:100%;margin:24px 0 5px}.note{font-size:14px}#status{min-height:2em}</style>
<main><h1>__TITLE__</h1><p>__INTRO__</p><label for="version">声音</label><select id="version">__VERSIONS__</select>
<label for="band">频段</label><select id="band">__BANDS__</select><label for="duration">片段</label><select id="duration">__DURATIONS__</select>
<audio id="player" controls preload="metadata"></audio><p id="status" class="note"></p>__NOTES__</main>
<script>const files=__FILES__,defaultVersion=__DEFAULT__;const version=document.getElementById('version'),band=document.getElementById('band'),duration=document.getElementById('duration'),player=document.getElementById('player'),status=document.getElementById('status');let revision=0;
function update(){const serial=++revision,playing=!player.paused,time=player.currentTime||0;player.pause();if(version.value==='reference')duration.value='short';player.src=files[version.value][band.value+'_'+duration.value];player.load();status.textContent=version.options[version.selectedIndex].text+' · '+band.options[band.selectedIndex].text;player.onloadedmetadata=()=>{if(serial!==revision)return;player.currentTime=Math.min(time,Math.max(0,player.duration-.02));if(playing)player.play().catch(()=>{});};}
version.addEventListener('change',update);band.addEventListener('change',update);duration.addEventListener('change',()=>{if(duration.value==='long'&&version.value==='reference')version.value=defaultVersion;update();});update();</script></html>'''
    values=dict(TITLE=html.escape(title),INTRO=html.escape(intro),
        VERSIONS=options(versions,default_version),BANDS=options(bands,'whole'),DURATIONS=options(durations,'short'),
        NOTES=''.join('<p class="note">'+html.escape(s)+'</p>' for s in notes),
        FILES=json.dumps(files,separators=(',',':')),DEFAULT=json.dumps(default_version if default_version!='reference' else next(k for k in versions if k!='reference')))
    for key,value in values.items():page=page.replace('__'+key+'__',value)
    return page

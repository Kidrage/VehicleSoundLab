'use strict';
const $=id=>document.getElementById(id);
let project=null,editedRows=null,editedRho=null,busy=false,noticeTimer;
const definitions=[
 ['pitch','音高比例',.9,1.1,.001,'×','有限变调，时长保持不变','toneControls'],
 ['gain_db','输出增益',-36,0,.5,' dB','直接写入导出模型的幅度','toneControls'],
 ['low_db','低频厚度',-12,12,.5,' dB','250 Hz以下现有DNA分音','toneControls'],
 ['mid_db','中频声线',-12,12,.5,' dB','250 Hz–2.5 kHz','toneControls'],
 ['high_db','高频亮度',-12,12,.5,' dB','2.5 kHz以上现有DNA分音','toneControls'],
 ['tilt','整体倾斜',-3,3,.1,' dB/oct','以1 kHz为中心调整谱形','toneControls'],
 ['detail','细节总量',0,1,.01,'','幅度变化的总量','detailControls'],
 ['shared','联动起伏',0,2,.01,'×','分音之间共有的统计变化','detailControls'],
 ['local','逐分音起伏',0,2,.01,'×','各分音内部的统计变化','detailControls'],
 ['width','左右宽度',0,1.5,.01,'×','参数域M/S；1×保留原始左右关系','detailControls']
];
for(const [id,label,min,max,step,unit,hint,group] of definitions){
 const box=document.createElement('div');box.className='control';
 box.innerHTML=`<div class="caption"><label for="${id}">${label}</label><output id="${id}Value"></output></div><input id="${id}" type="range" min="${min}" max="${max}" step="${step}"><small>${hint}</small>`;
 $(group).append(box);$(id).addEventListener('input',()=>{readouts();chart();markDirty();});
}
function notice(text,error=false,loading=false){clearTimeout(noticeTimer);$('toast').textContent=text;$('toast').className=error?'error':loading?'busy':'';if(!loading)noticeTimer=setTimeout(()=>$('toast').classList.add('quiet'),6000);}
function markDirty(){if(project?.model){$('renderInfo').textContent='参数已改动 · 请重新生成试听';$('storage').textContent='参数尚未保存 · 生成试听或点击“保存参数”';}}
function readouts(){for(const [id,,,,step,unit] of definitions)$(id+'Value').textContent=Number($(id).value).toFixed(step>=.5?1:id==='pitch'?3:2)+unit;}
function params(){const p={};for(const [id] of definitions)p[id]=Number($(id).value);p.seconds=Number($('seconds').value);p.seed=Number($('seed').value);return p;}
function setParams(p){for(const [id] of definitions)$(id).value=p[id];$('seconds').value=p.seconds;$('seed').value=p.seed;readouts();chart();}
function lock(value){busy=value;document.querySelectorAll('button').forEach(b=>b.disabled=value);if(!value){$('compile').disabled=!project?.has_audio;$('analyze').disabled=!project?.has_audio;$('render').disabled=!project?.model;$('save').disabled=!project?.model;$('analysisDownload').disabled=!project?.analysis;}window.DesignAudition.updateButtons(value);}
async function request(url,data){const response=await fetch(url,data===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});const value=await response.json();if(!response.ok)throw Error(value.error||'请求失败');return value;}
async function task(url,data,message){lock(true);notice(message,false,true);try{const {job}=await request(url,data);for(;;){await new Promise(r=>setTimeout(r,350));const value=await request('/api/job/'+job);if(value.status==='error')throw Error(value.error);if(value.status==='done')return value.result;}}finally{lock(false);}}
async function guarded(action){try{await action();}catch(error){notice(error.message,true);}}
function load(p){
 document.querySelectorAll('audio').forEach(audio=>audio.pause());
 project=p;editedRows=p.rows?structuredClone(p.rows):null;editedRho=p.rho?structuredClone(p.rho):null;
 $('name').value=p.name;$('projectLabel').textContent=p.name;$('state').value=p.state;$('viewpoint').value=p.viewpoint;
 if(p.reference_url){$('reference').src=p.reference_url+'?v='+Date.now();}else{$('reference').removeAttribute('src');$('reference').load();}
 if(p.selection){$('start').value=p.selection[0];$('end').value=p.selection[1];}
 if(p.analysis){const a=p.analysis;$('sourceInfo').textContent=`${a.seconds.toFixed(2)}s · ${a.rate/1000}k · ${a.channels}ch`;
  $('root').value=(a.root_hz||0).toFixed(3);$('candidates').replaceChildren();
  for(const c of a.root_candidates.slice(0,5)){const b=document.createElement('button');b.textContent=c.hz.toFixed(2)+' Hz';b.onclick=()=>{$('root').value=c.hz.toFixed(3);rootBudget();notice('已选择候选基频，请重新分析选区确认。');};$('candidates').append(b);}
  $('analysisNote').textContent=a.stable_candidate?'选区内声学周期相对稳定。确认基频后可提取固定音色参数；基频仍可能有倍频／分频歧义。':`周期不稳定或证据不足${a.pitch_drift!==null?'（观察变化约'+(a.pitch_drift*100).toFixed(1)+'%）':''}。可导出分析轨迹，或缩短选区；固定草稿不复现加速过程。`;
 }else{$('sourceInfo').textContent='现有参数预设';$('candidates').replaceChildren();$('root').value=p.model?.root_hz||46.875;$('analysisNote').textContent='当前载入模型参数；如需提取新声纹，请先导入单一状态的音频片段。';}
 if(p.model){$('modelInfo').textContent=`${p.model.harmonics}阶 · ${p.model.components}个联动成分 · 基频 ${p.model.root_hz.toFixed(3)} Hz · 分音上限 ${(p.model.root_hz*p.model.harmonics/1000).toFixed(1)} kHz`;$('harmonics').value=p.model.harmonics;$('components').value=p.model.components;}else $('modelInfo').textContent='先确认基频，再提取参数';
 buildTable();setParams(p.params);drawWave();lock(false);
 rootBudget();refreshProjects().catch(()=>{});$('storage').textContent='已保存本地工程 · '+p.id.slice(0,8);
 localStorage.setItem('vslSoundProject',p.id);
 if(p.last_version){const prefix=`/files/${p.id}/${p.last_version}/`;setAudio({audio:prefix+'preview.wav',bundle:prefix+'sound-design.zip',parameters:prefix+'parameters.json',csv:prefix+'harmonics.csv'},p.render_report);}
 else{$('preview').removeAttribute('src');$('preview').load();$('downloads').replaceChildren();$('renderInfo').textContent='由现有C算法生成';}
 if(p.preview_stale)$('renderInfo').textContent='参数已保存 · 已有试听对应上次生成';
 $('sourceBinding').textContent=p.reference_matches_model===false?'参考选区或基频已改变。当前试听仍用上次提取模型；重新提取后才更新声源。':p.reference_matches_model===true?'当前参考与模型提取来源一致。':p.has_audio&&p.model?'旧模型尚无参考绑定记录，重新提取后建立。':'';
 window.DesignHistory.refresh(p).catch(error=>notice(error.message,true));window.DesignAudition.update(p);
}
async function refreshProjects(){const list=await request('/api/projects');$('projects').replaceChildren();const placeholder=document.createElement('option');placeholder.value='';placeholder.textContent='选择已保存的音色…';$('projects').append(placeholder);for(const p of list){const option=document.createElement('option');option.value=p.id;option.textContent=p.name+' · '+p.id.slice(0,6);$('projects').append(option);}$('projects').value=project?.id||'';}
$('projects').onchange=()=>guarded(async()=>{if(busy||!$('projects').value)return;load(await request('/api/project/'+$('projects').value));notice('已打开本地工程。');});
function buildTable(){
 const body=$('harmonicRows');body.replaceChildren();if(!project?.model){$('rho').value='';return;}
 const rows=editedRows||project.model.rows;
 for(let i=0;i<rows.length;i++){const row=rows[i],tr=document.createElement('tr');for(const key of ['order','hz','left','right','phase_l','phase_r','residual_rho']){const td=document.createElement('td');if(key==='order'||key==='hz')td.textContent=key==='order'?row[key]:row[key].toFixed(1);else{const input=document.createElement('input');input.type='number';input.step=key.includes('phase')?'.1':'.00001';input.value=Number(row[key].toPrecision(9));input.setAttribute('aria-label',`${i+1}阶 ${key}`);input.onchange=()=>{if(!editedRows)editedRows=structuredClone(project.model.rows);editedRows[i][key]=Number(input.value);chart();markDirty();notice('分音参数已修改，生成试听后保存。');};td.append(input);}tr.append(td);}body.append(tr);}
 $('rho').value=(editedRho||project.model.rho).map(v=>Number(v.toPrecision(9))).join(', ');
}
$('rho').onchange=()=>{editedRho=$('rho').value.trim()?$('rho').value.split(',').map(Number):[];markDirty();};
function canvas(id,height){const c=$(id),ratio=devicePixelRatio||1,w=Math.max(200,c.parentElement.clientWidth-(id==='spectrum'?30:0));c.style.height=height+'px';c.width=w*ratio;c.height=height*ratio;const ctx=c.getContext('2d');ctx.scale(ratio,ratio);return [ctx,w,height];}
function drawWave(){const [ctx,w,h]=canvas('waveform',64);const values=project?.analysis?.waveform||[];ctx.strokeStyle='#7bcac1';ctx.lineWidth=1;ctx.beginPath();values.forEach((v,i)=>{const x=i/values.length*w;ctx.moveTo(x,h/2-v*h*.44);ctx.lineTo(x,h/2+v*h*.44);});ctx.stroke();}
function chart(){const [ctx,w,h]=canvas('spectrum',150),left=8,right=w-8;const x=f=>left+Math.log10(Math.max(20,f)/20)/3*(right-left);for(const f of [100,1000,10000]){ctx.strokeStyle='#293a2d';ctx.beginPath();ctx.moveTo(x(f),0);ctx.lineTo(x(f),h);ctx.stroke();ctx.fillStyle='#69806d';ctx.font='9px Segoe UI';ctx.fillText(f>=1000?f/1000+'k':f,x(f)+4,h-5);}
 if(project?.analysis){const a=project.analysis,peak=Math.max(...a.spectrum_db);ctx.beginPath();ctx.strokeStyle='#5a6b67';a.spectrum_hz.forEach((f,i)=>{if(f<20||f>20000)return;const y=h-12-Math.max(0,Math.min(80,a.spectrum_db[i]-peak+80))/80*(h-20);i?ctx.lineTo(x(f),y):ctx.moveTo(x(f),y);});ctx.stroke();}
 if(!project?.model)return;const p=params(),rows=editedRows||project.model.rows;const levels=rows.map(r=>{const band=r.hz<250?p.low_db:r.hz<2500?p.mid_db:p.high_db;return 20*Math.log10(Math.max(Math.hypot(r.left,r.right),1e-12))+band+p.tilt*Math.log2(Math.max(20,r.hz)/1000);});const peak=Math.max(...levels);ctx.strokeStyle='#b9e286';rows.forEach((r,i)=>{if(r.hz>20000)return;const height=Math.max(0,Math.min(80,levels[i]-peak+80))/80*(h-20);ctx.beginPath();ctx.moveTo(x(r.hz),h-12);ctx.lineTo(x(r.hz),h-12-height);ctx.stroke();});}
function rootBudget(maximize=false){const root=Number($('root').value),limit=Math.min(320,Math.floor(21600/(root*1.1)));if(root>0&&limit>=1){$('harmonics').max=limit;if(maximize||Number($('harmonics').value)>limit)$('harmonics').value=limit;$('bandwidth').textContent=`预计分音上限 ${(root*Number($('harmonics').value)/1000).toFixed(1)} kHz。上限外的原声细节不会自动保留；低基频尤其需要检查。`;}}
$('root').onchange=()=>rootBudget();$('harmonics').onchange=()=>rootBudget();
async function openPreset(preset){load(await task('/api/new',{preset},'载入现有参数…'));notice('已载入。调整参数后点击“生成 C 试听”。');}
document.querySelectorAll('[data-preset]').forEach(b=>b.onclick=()=>guarded(()=>openPreset(b.dataset.preset)));
$('audioFile').onchange=()=>guarded(async()=>{const file=$('audioFile').files[0];if(!file)return;if(file.size>48*1024**2)throw Error('请选择小于48MB的片段');const encoded=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result.split(',')[1]);reader.onerror=reject;reader.readAsDataURL(file);});load(await task('/api/new',{filename:file.name,audio:encoded,state:$('state').value,viewpoint:$('viewpoint').value},'分析片段：波形、频谱、周期与左右关系…'));rootBudget(true);notice('已分析。请确认声学基频，再提取参数。');});
function designDraft(){return {name:$('name').value,params:params(),rows:editedRows,rho:editedRho,state:$('state').value,viewpoint:$('viewpoint').value};}
async function savePending(){if(project?.model)await task('/api/save',{id:project.id,...designDraft()},'保留当前调参…');}
function analysisRequest(){return {id:project.id,start:Number($('start').value),end:Number($('end').value),root_hz:Number($('root').value)||null,name:$('name').value,state:$('state').value,viewpoint:$('viewpoint').value,draft:project?.model?designDraft():null};}
$('analyze').onclick=()=>guarded(async()=>{load(await task('/api/analyze',analysisRequest(),'重新分析选区…'));notice('选区分析完成。');});
$('compile').onclick=()=>guarded(async()=>{const state=$('state').value,viewpoint=$('viewpoint').value;const h=Number($('harmonics').value),k=Number($('components').value),root=Number($('root').value);load(await task('/api/analyze',analysisRequest(),'确认选区与基频…'));load(await task('/api/compile',{id:project.id,root_hz:root,harmonics:h,components:k,allow_unstable:$('allowUnstable').checked,state,viewpoint},'提取统计参数：平均声线、联动与逐分音变化…'));notice('参数已生成。接下来可调音、试听和导出。');});
function setAudio(result,report){$('preview').src=result.audio+'?v='+Date.now();$('preview').loop=$('loop').checked;$('downloads').replaceChildren();for(const [label,key] of [['工程与C模型 ZIP','bundle'],['完整参数 JSON','parameters'],['分音表 CSV','csv']]){const a=document.createElement('a');a.textContent=label;a.href=result[key];a.download='';$('downloads').append(a);}if(report)$('renderInfo').textContent=`峰值 ${report.peak.toFixed(3)} · ${report.rms_dbfs.toFixed(1)} dBFS`;
 if(report?.overload)notice('预览峰值超过1，请降低输出增益后重新生成。',true);}
$('render').onclick=()=>guarded(async()=>{const result=await task('/api/render',{id:project.id,name:$('name').value,params:params(),rows:editedRows,rho:editedRho,state:$('state').value,viewpoint:$('viewpoint').value},'现有C声源正在生成试听并保存参数版本…');load(result.project);if(!result.project.render_report.overload)notice('试听已生成，当前参数已保存。点击播放器开始监听。');});
$('save').onclick=()=>guarded(async()=>{load(await task('/api/save',{id:project.id,name:$('name').value,params:params(),rows:editedRows,rho:editedRho,state:$('state').value,viewpoint:$('viewpoint').value},'保存参数…'));notice('参数已保存，可从“打开本地工程”重新载入。');});
for(const id of ['name','state','viewpoint','seconds','seed'])$(id).addEventListener('change',markDirty);
$('loop').onchange=()=>{$('preview').loop=$('loop').checked;};
$('reset').onclick=()=>{if(!project)return;editedRows=null;editedRho=null;setParams({pitch:1,detail:1,gain_db:-6,low_db:0,mid_db:0,high_db:0,tilt:0,width:1,shared:1,local:1,seconds:4,seed:48271});buildTable();markDirty();notice('已恢复基础参数；生成试听后保存。');};
const recipes={body:{low_db:3,high_db:-1,tilt:-.3,shared:.7,local:.6},bright:{high_db:3,tilt:.4,detail:.7},motion:{detail:.7,shared:.6,local:.25},sci:{detail:.2,shared:.3,local:.1,width:1.1}};
document.querySelectorAll('[data-recipe]').forEach(b=>b.onclick=()=>{for(const [key,value]of Object.entries(recipes[b.dataset.recipe]))$(key).value=value;readouts();chart();markDirty();notice('调音手法已应用；生成试听比较变化。');});
$('presetFile').onchange=()=>guarded(async()=>{const file=$('presetFile').files[0];if(!file)return;const p=JSON.parse(await file.text());load(await task('/api/new',{package:p},'恢复完整参数…'));notice('预设已恢复，不依赖原始音频。');});
$('loadJson').onclick=()=>guarded(async()=>{if(!project?.model)throw Error('请先载入模型');const p=await request('/api/parameters/'+project.id);p.name=$('name').value;p.state=$('state').value;p.viewpoint=$('viewpoint').value;p.params=params();p.rows=editedRows;p.rho=editedRho;$('jsonEditor').value=JSON.stringify(p,null,2);notice('可直接编辑完整参数，验证后作为新音色载入。');});
$('applyJson').onclick=()=>guarded(async()=>{load(await task('/api/new',{package:JSON.parse($('jsonEditor').value)},'校验完整参数…'));notice('完整参数验证通过。已创建独立音色。');});
$('analysisDownload').onclick=()=>{if(!project?.analysis)return;const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify({name:project.name,state:$('state').value,viewpoint:$('viewpoint').value,source:project.source,selection:project.selection,...project.analysis},null,2)],{type:'application/json'}));a.download='voice-analysis.json';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000);};
$('driver').onclick=()=>guarded(async()=>{await request('/api/driver',{});notice('已打开现有原生驾驶窗口；该窗口独立控制驾驶与声层。');});
window.DesignAudition.setup(notice);
window.DesignHistory.setup({getProject:()=>project,request,task,load,notice,guarded,savePending});
window.addEventListener('resize',()=>{drawWave();chart();});
guarded(async()=>{const config=await request('/api/config');$('storage').textContent='本地工程目录 · '+config.root;const previous=new URLSearchParams(location.search).get('project')||localStorage.getItem('vslSoundProject');if(previous){try{load(await request('/api/project/'+previous));notice('已恢复上次音色工程。');return;}catch{}}await openPreset('v10');});

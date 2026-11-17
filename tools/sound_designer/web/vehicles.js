'use strict';
const $=id=>document.getElementById(id);
const labels={base:['默认 / 巡航','启动与接火阶段也沿用此主声线；至少选择一个工程。'],idle:['怠速','运行后进入怠速时采用。'],power:['给油 / 加速','给油、补油和换挡恢复时采用。'],overrun:['收油 / 减速','收油和换挡切断时采用。']};
let choices=[],current=null,groups={base:[],idle:[],power:[],overrun:[]},busy=false;
function status(text,error=false){$('status').textContent=text;$('status').classList.toggle('error',error);}
async function request(url,data){const r=await fetch(url,data===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});const v=await r.json();if(!r.ok)throw Error(v.error||'请求失败');return v;}
async function guarded(action){if(busy)return;busy=true;setDisabled(true);try{await action();}catch(e){status(e.message,true);}finally{busy=false;setDisabled(false);}}
function setDisabled(value){document.querySelectorAll('button,input,select').forEach(e=>e.disabled=value);$('versions').disabled=value||!current;for(const card of document.querySelectorAll('[data-group]'))card.querySelector('.add').disabled=value||groups[card.dataset.group].length>=8;window.VehicleSystem.lock(value);}
function option(value,text){const o=document.createElement('option');o.value=value;o.textContent=text;return o;}
function dirty(){status('配方有未保存修改。编译保存后会生成新的系数快照。');}
function renderGroups(){
 $('groups').replaceChildren();
 for(const [key,[label,description]] of Object.entries(labels)){
  const card=document.createElement('section');card.className='card';card.dataset.group=key;
  const title=document.createElement('h2');title.textContent=label;card.append(title);
  const p=document.createElement('p');p.className='hint';p.textContent=description;card.append(p);
  groups[key].forEach((value,index)=>{
   const row=document.createElement('div');row.className='anchor-row';const select=document.createElement('select');select.setAttribute('aria-label',label+'锚点'+(index+1));
   select.append(option('','选择已保存的声纹…'));for(const c of choices)select.append(option(c.id,c.name));
   if(value&&!choices.some(c=>c.id===value))select.append(option(value,'来源工程已不存在'));
   select.value=value;select.onchange=()=>{groups[key][index]=select.value;renderGroups();dirty();};row.append(select);
   const remove=document.createElement('button');remove.textContent='×';remove.setAttribute('aria-label','移除'+label+'锚点'+(index+1));remove.onclick=()=>{groups[key].splice(index,1);renderGroups();dirty();};row.append(remove);
   const meta=document.createElement('span');meta.className='anchor-meta';const c=choices.find(c=>c.id===value);
   if(c){meta.textContent=`${c.base_hz.toFixed(3)} Hz · ${c.harmonics} 分音 · ${c.state} · ${c.viewpoint}`;const link=document.createElement('a');link.href='/index.html?project='+c.id;link.textContent=' 编辑声纹 ↗';meta.append(link);}row.append(meta);card.append(row);
  });
  const add=document.createElement('button');add.className='add';add.textContent='＋ 加入声纹锚点';add.disabled=groups[key].length>=8;add.onclick=()=>{if(groups[key].length<8){groups[key].push('');renderGroups();dirty();}};card.append(add);$('groups').append(card);
 }
}
async function refresh(){choices=await request('/api/state-recipes/projects');const list=await request('/api/state-recipes');$('recipes').replaceChildren(option('','新配方'));for(const r of list)$('recipes').append(option(r.id,r.name));if(current)$('recipes').value=current.id;}
function load(value){
 current=value;const c=value.configuration;groups=structuredClone(c.groups);$('name').value=c.name;$('rpm').value=c.reference_rpm;$('transition').value=c.transition_seconds;$('detail').value=c.detail*100;$('seed').value=c.seed;
 $('recipes').value=value.id;$('versions').replaceChildren();for(const v of value.versions)$('versions').append(option(v.version,`${v.created.slice(0,19).replace('T',' ')} · ${v.name}`));$('versions').value=value.version;
 $('downloads').replaceChildren();for(const [key,label]of [['bank','下载车辆 DNA 参数包'],['preset','下载整车参数'],['provenance','下载来源与映射记录']]){if(!value[key])continue;const a=document.createElement('a');a.href=value[key];a.download='';a.textContent=label;$('downloads').append(a);}
 $('coverage').textContent=value.coverage;$('sourceStatus').classList.toggle('changed',value.changed_sources.length>0);$('sourceStatus').textContent=value.changed_sources.length?`${value.changed_sources.length} 个来源工程已更改或缺失。此快照保持原系数；再次编译才会采用当前工程。`:'来源与保存时一致。此参数包可脱离原音频使用。';
 window.VehicleSystem.load(c.system);$('systemNotes').textContent=(value.system_notes||[]).join('；');if(value.changed_events?.length)$('sourceStatus').textContent+=` ${value.changed_events.length} 个事件来源已更改或缺失。`;
 localStorage.setItem('vslStateRecipe',value.id);renderGroups();
}
$('save').onclick=()=>guarded(async()=>{
 if(Object.values(groups).some(g=>g.some(x=>!x)))throw Error('请先选择每个已加入锚点的声纹工程，或移除空行');
 const configuration={name:$('name').value,groups,reference_rpm:Number($('rpm').value),transition_seconds:Number($('transition').value),detail:Number($('detail').value)/100,seed:Number($('seed').value)};
 const system=window.VehicleSystem.get();if(system)configuration.system=system;
 const job=await request('/api/state-recipes/save',{id:current?.id||null,configuration});status('正在编译已保存声纹…');
 let value;for(let i=0;i<600;i++){value=await request('/api/job/'+job.job);if(value.status==='done'||value.status==='error')break;await new Promise(r=>setTimeout(r,100));}
 if(value.status!=='done')throw Error(value.error||'编译尚未返回，请稍后重新打开已保存配方');
 await refresh();load(value.result);status(value.result.preset?'整车参数已保存。下载“整车参数”，在独立窗口用“载入参数”打开。':'车辆 DNA 已保存。下载参数包，在独立驾驶窗口导入即可试听。');
});
$('recipes').onchange=()=>{const selected=$('recipes').value;if(!selected){$('new').click();return;}guarded(async()=>{await refresh();load(await request('/api/state-recipes/view/'+selected));status('已打开保存的车辆 DNA。');});};
$('versions').onchange=()=>guarded(async()=>{load(await request('/api/state-recipes/view/'+current.id+'/'+$('versions').value));status('已打开历史系数快照。再次编译会读取当前声纹工程，并保存为新版本。');});
$('new').onclick=()=>{current=null;groups={base:[''],idle:[],power:[],overrun:[]};$('recipes').value='';$('name').value='我的车辆 DNA';$('rpm').value=3000;$('transition').value=.12;$('detail').value=65;$('seed').value=48271;$('downloads').replaceChildren();$('versions').replaceChildren(option('','保存后显示'));$('versions').disabled=true;$('sourceStatus').textContent='';$('coverage').textContent='请选择默认声纹，其他状态可按需添加。';window.VehicleSystem.load();$('systemNotes').textContent='';localStorage.removeItem('vslStateRecipe');renderGroups();dirty();};
$('driver').onclick=()=>guarded(async()=>{const v=await request('/api/driver',{});status((v.already_open?'独立窗口已在运行。':'独立窗口已打开。')+(current?.preset?'停止监听后，用“载入参数”打开下载的整车参数。':'请在 DNA 配方页导入参数包。'));});
for(const id of ['name','rpm','transition','detail','seed'])$(id).addEventListener('input',dirty);
guarded(async()=>{window.VehicleSystem.setup(await request('/api/state-recipes/system'),dirty);await refresh();const previous=localStorage.getItem('vslStateRecipe');if(previous){try{load(await request('/api/state-recipes/view/'+previous));status('已恢复上次车辆 DNA。');return;}catch(e){status(e.message,true);}}groups.base=[''];renderGroups();status(choices.length?'先选择默认声纹，再按需加入其他状态。':'还没有已提取声纹。请先到“声纹设计”创建并保存一个音色。');});

/* Startup, event selection and generic layers; no vehicle-state logic here. */
window.VehicleSystem=(()=>{
 let meta=null,busy=false;
 const $=id=>document.getElementById(id),fields={};
 function number(parent,path,label,value,min,max,step){const box=document.createElement('label');box.textContent=label;const input=document.createElement('input');input.type='number';input.min=min;input.max=max;input.step=step;input.value=value;input.dataset.systemField=path;input.setAttribute('aria-label',label);fields[path]=input;box.append(input);parent.append(box);}
 function details(title){const d=document.createElement('details'),s=document.createElement('summary');s.textContent=title;d.append(s);const body=document.createElement('div');body.className='system-grid';d.append(body);$('systemFields').append(d);return body;}
 function setup(data,dirty){
  meta=data;const defaults=data.defaults;
  let dnaBody=details('DNA · 声线与空气纹理');for(const [key,label,min,max]of data.dna_fields)number(dnaBody,'dna.'+key,label,defaults.dna[key],min,max,.01);
  data.dna_states.forEach((label,i)=>{for(const [key,title]of [['line_state','声线'],['air_state','纹理']])number(dnaBody,'dna.'+key+'.'+i,label+' · '+title,1,0,2,.05);});
  let body=details('启动响应');for(const [key,label,min,max]of data.startup_fields)number(body,'startup.'+key,label,defaults.startup[key],min,max,.001);
  body=details('独立事件');const enabled=document.createElement('label');enabled.className='check';const check=document.createElement('input');check.type='checkbox';check.id='systemEventsEnabled';enabled.append(check,document.createTextNode('自动触发所选事件'));body.append(enabled);
  for(const {key,label}of data.kinds){
   const box=document.createElement('label');box.className='system-event';box.textContent=label;const select=document.createElement('select');select.dataset.eventKind=key;select.append(new Option('不启用此事件',''));
   for(const p of data.projects.filter(p=>p.kind===key))select.append(new Option(p.name+(p.band_limited?' · 频带候选':'')+(!p.physical_identity_confirmed?' · 类型待确认':''),p.id));
   fields['event.'+key]=select;box.append(select);body.append(box);
   number(body,'level.'+key,label+'电平 · %',100,0,100,1);
  }
  for(const [key,label,min,max,step]of data.macro_fields)number(body,'macro.'+key,label,defaults.events[key],min,max,step);
  body=details('事件时序与概率');for(const [key,label,min,max,step]of data.policy_fields)number(body,'policy.'+key,label,defaults.policy[key],min,max,step);
  body=details('连续辅助层');for(const [key,label]of data.layer_fields)number(body,'layer.'+key,label+' · %',0,0,100,1);
  $('systemFields').addEventListener('input',dirty);$('systemFields').addEventListener('change',dirty);
  $('includeSystem').addEventListener('change',()=>{lock(busy);dirty();});load(null);
 }
 function lock(value){busy=value;if(!meta)return;for(const input of $('systemFields').querySelectorAll('input,select'))input.disabled=value||!$('includeSystem').checked;}
 function load(value){
  if(!meta)return;const s=value||structuredClone(meta.defaults);s.dna??=structuredClone(meta.defaults.dna);$('includeSystem').checked=Boolean(value);$('systemEventsEnabled').checked=s.events.enabled;
  for(const [key]of meta.dna_fields)fields['dna.'+key].value=s.dna[key];
  for(const key of ['line_state','air_state'])s.dna[key].forEach((v,i)=>fields['dna.'+key+'.'+i].value=v);
  for(const [key,v]of Object.entries(s.startup))fields['startup.'+key].value=v;
  for(const [key,v]of Object.entries(s.policy))fields['policy.'+key].value=v;
  for(const [key,v]of Object.entries(s.layers))fields['layer.'+key].value=v*100;
  for(const [key]of meta.macro_fields)fields['macro.'+key].value=s.events[key];
  meta.kinds.forEach(({key},i)=>{const id=s.events.projects[key]||'',select=fields['event.'+key];if(id&&![...select.options].some(o=>o.value===id))select.append(new Option('原事件工程已缺失',id));select.value=id;fields['level.'+key].value=s.events.levels[i]*100;});lock(busy);
 }
 function get(){
  if(!meta||!$('includeSystem').checked)return undefined;
  const s=structuredClone(meta.defaults);s.events.enabled=$('systemEventsEnabled').checked;
  for(const [key]of meta.dna_fields)s.dna[key]=Number(fields['dna.'+key].value);
  for(const key of ['line_state','air_state'])s.dna[key]=s.dna[key].map((v,i)=>Number(fields['dna.'+key+'.'+i].value));
  for(const key of Object.keys(s.startup))s.startup[key]=Number(fields['startup.'+key].value);
  for(const key of Object.keys(s.policy))s.policy[key]=Number(fields['policy.'+key].value);
  for(const key of Object.keys(s.layers))s.layers[key]=Number(fields['layer.'+key].value)/100;
  for(const [key]of meta.macro_fields)s.events[key]=Number(fields['macro.'+key].value);
  meta.kinds.forEach(({key},i)=>{s.events.projects[key]=fields['event.'+key].value||null;s.events.levels[i]=Number(fields['level.'+key].value)/100;});return s;
 }
 return {setup,load,get,lock};
})();

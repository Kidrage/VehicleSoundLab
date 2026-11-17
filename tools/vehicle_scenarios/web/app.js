(() => {
  'use strict';
  const data = window.VSL_LIFECYCLE;
  const audio = document.querySelector('#audio');
  const select = document.querySelector('#track');
  const plot = document.querySelector('#plot');
  const rows = data.telemetry;
  if(data.introduction)document.querySelector('.intro').textContent=data.introduction;
  if(data.listening_hint)document.querySelector('#message').textContent=data.listening_hint;
  const life = {OFF:'熄火',READY:'就绪',CRANK:'拖转',CATCH:'接火',RUNNING:'运行',STOPPING:'停机'};
  const op = {IDLE:'怠速',FREE_REV:'补油',PULL:'加速',CRUISE:'巡航',OVERRUN:'收油',SHIFT_CUT:'换挡切断',SHIFT_RECOVER:'换挡恢复',REV_MATCH:'降挡补油'};
  const names = {OFF:'熄火',START:'启动',LAUNCH:'起步',ACCELERATE:'加速',LIFT:'收油',BRAKE:'制动降挡',STOPPED_IDLE:'停车怠速',PARKED_IDLE:'停车怠速',IGNITION_OFF:'熄火'};
  let serial = 0, loading = false, pending;
  const cache = new Map(), urls = new Set();
  data.tracks.forEach(track => select.add(new Option(track.name,track.id)));
  audio.volume = 1;
  async function asset(file) {
    if(location.protocol==='file:')return new URL(file,location.href).href;
    if(!cache.has(file))cache.set(file,(async()=>{
      const response=await fetch(file);if(!response.ok)throw Error('音频载入失败：'+response.status);
      const url=URL.createObjectURL(await response.blob());urls.add(url);return url;
    })().catch(error=>{cache.delete(file);throw error;}));
    return cache.get(file);
  }
  function currentRow(seconds) {
    let low=0, high=rows.length-1;
    while(low<high){const middle=Math.ceil((low+high)/2);if(rows[middle][0]<=seconds)low=middle;else high=middle-1;}
    return rows[low];
  }
  function draw() {
    const rect=plot.getBoundingClientRect(), scale=window.devicePixelRatio||1;
    plot.width=Math.round(rect.width*scale);plot.height=Math.round(250*scale);
    const ctx=plot.getContext('2d');ctx.scale(scale,scale);
    const w=rect.width, h=250, left=46, right=w-38, top=18, bottom=220;
    const x=t=>left+(right-left)*t/data.duration;
    ctx.font='11px Segoe UI, sans-serif';ctx.strokeStyle='#e8edf3';ctx.fillStyle='#8391a2';ctx.lineWidth=1;
    [0,2000,4000,6000,8000].forEach(r=>{const y=bottom-(bottom-top)*r/9000;ctx.beginPath();ctx.moveTo(left,y);ctx.lineTo(right,y);ctx.stroke();ctx.fillText(String(r),2,y+4);});
    for(let t=0;t<=data.duration;t+=4)ctx.fillText(t+'s',x(t)-6,241);
    data.stages.filter(s=>s.seconds>0&&s.seconds<data.duration).forEach(s=>{ctx.strokeStyle='#edf0f5';ctx.beginPath();ctx.moveTo(x(s.seconds),top);ctx.lineTo(x(s.seconds),bottom);ctx.stroke();});
    [[1,9000,'#2364c9'],[2,250,'#219681']].forEach(([column,max,color])=>{
      ctx.strokeStyle=color;ctx.lineWidth=1.5;ctx.beginPath();rows.forEach((row,i)=>{const y=bottom-(bottom-top)*Math.min(max,row[column])/max;if(i)ctx.lineTo(x(row[0]),y);else ctx.moveTo(x(row[0]),y);});ctx.stroke();
    });
    ctx.fillStyle='#219681';ctx.fillText('250',right+6,top+5);ctx.fillText('0',right+6,bottom+3);
    ctx.strokeStyle='#152b46';ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(x(audio.currentTime),top);ctx.lineTo(x(audio.currentTime),bottom);ctx.stroke();
  }
  function update() {
    const row=currentRow(audio.currentTime);
    document.querySelector('#rpm').textContent=Math.round(row[1]).toLocaleString();
    document.querySelector('#speed').textContent=row[2].toFixed(1);
    document.querySelector('#gear').textContent=row[3]||'N';
    document.querySelector('#state').textContent=life[row[4]]+' · '+op[row[5]];
    document.querySelector('#throttle').value=row[6];document.querySelector('#brake').value=row[7];
    draw();
  }
  async function switchTrack() {
    const state=loading?{...pending}:{time:audio.currentTime,playing:!audio.paused,volume:audio.volume};
    const token=++serial;pending=state;loading=true;
    const track=data.tracks.find(t=>t.id===select.value);
    audio.pause();
    try {
      const url=await asset(track.file);if(token!==serial)return;
      audio.onloadedmetadata=async()=>{
        if(token!==serial || audio.currentSrc!==url)return;
        audio.currentTime=Math.min(state.time,Math.max(0,audio.duration-.001));audio.volume=state.volume;loading=false;update();
        document.querySelector('#message').textContent='当前监听：'+track.name+'。切换声层保留时间和音量。';
        if(state.playing){try{await audio.play();}catch{if(token===serial)document.querySelector('#message').textContent='声层已切换，点击播放继续。';}}
      };
      audio.src=url;audio.dataset.source=track.file;audio.load();
    } catch(error) {
      if(token===serial){loading=false;document.querySelector('#message').textContent=error.message;}
    }
  }
  select.addEventListener('change',switchTrack);
  data.stages.filter(s=>s.name!=='END'&&s.name!=='OFF').forEach(s=>{
    const button=document.createElement('button');button.textContent=names[s.name]+' '+s.seconds.toLocaleString('en',{maximumFractionDigits:2})+'s';
    button.addEventListener('click',()=>{audio.currentTime=s.seconds;update();});document.querySelector('#stages').append(button);
  });
  plot.addEventListener('click',event=>{const r=plot.getBoundingClientRect();audio.currentTime=Math.max(0,Math.min(data.duration-.001,(event.clientX-r.left-46)/(r.width-84)*data.duration));update();});
  ['timeupdate','seeked','loadedmetadata','pause'].forEach(event=>audio.addEventListener(event,update));
  new ResizeObserver(update).observe(plot);
  window.addEventListener('pagehide',()=>{for(const url of urls)URL.revokeObjectURL(url);});
  switchTrack();
  update();
})();

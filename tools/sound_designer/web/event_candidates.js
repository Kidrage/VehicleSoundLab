'use strict';
class VslEventCandidates {
 constructor(select){this.select=select;this.project=null;this.busy=false;document.getElementById('candidateAll').onchange=()=>this.show();}
 update(project,busy){this.project=project;this.busy=busy;this.show();}
 show(){
  const $=id=>document.getElementById(id),p=this.project,r=p?.candidate_scan;
  $('scanCandidates').disabled=this.busy||!p?.audio;$('scanDetector').disabled=this.busy||!p?.audio;$('candidateAll').disabled=this.busy||!r;
  $('candidateRows').replaceChildren();$('candidateReport').hidden=!p?.scan_report_url;
  if(p?.scan_report_url)$('candidateReport').href=p.scan_report_url;
  if(!r){$('candidateInfo').textContent='在整段导入音频中查找短瞬态，不自动判断回火或换挡，也不生成音色参数。';return;}
  const family=r.detector.family==='short_high'?'短促高频（16毫秒窗）':r.detector.family==='low_mid'?'低中频':'高频';
  $('candidateInfo').textContent=`${family}扫描：${r.candidates.length}处候选 · ${r.both_above_3db}处同时高于前后背景3 dB。全部仍需核对原声和动作。`;
  for(const [index,row] of r.candidates.entries()){
   if(!$('candidateAll').checked&&!row.both_full_band_above_3db)continue;
   const button=document.createElement('button');button.type='button';button.disabled=this.busy;
   button.dataset.candidateIndex=String(index);
   const at=document.createElement('strong');at.textContent=row.source_seconds.toFixed(3)+' s';
   const info=document.createElement('small');info.textContent=`前 ${row.contrast_db.before.toFixed(1)} / 后 ${row.contrast_db.after.toFixed(1)} dB · ${row.both_full_band_above_3db?'待核查':'弱对比'}`;
   button.append(at,info);button.setAttribute('aria-label','核查 '+row.source_seconds.toFixed(3)+' 秒候选');
   button.setAttribute('aria-pressed',String(p.selected_candidate?.scan_run===p.scan_run&&p.selected_candidate.index===index));
   button.onclick=()=>this.select(index,p.scan_run);$('candidateRows').append(button);
  }
  if(!$('candidateRows').children.length){const note=document.createElement('p');note.className='hint';note.textContent=r.candidates.length?'没有同时满足前后背景对比的候选，可展开全部候选核查。':'本段未检出符合固定瞬态规则的候选。';$('candidateRows').append(note);}
 }
}

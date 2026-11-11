"""Bind a concrete review proposal to public-page evidence; approves nothing."""
import hashlib
import json
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'research/calibration_candidates_v1'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    target=OUT/'review_proposal.json'
    if target.exists():raise SystemExit('Preserve finished reference proposal.')
    searches=json.loads((OUT/'search_catalog.json').read_text(encoding='utf-8'))
    rows=json.loads((OUT/'watch_metadata.json').read_text(encoding='utf-8'))
    by_id={r['id']:r for r in rows}
    selected=[]
    for label,key,seconds in [('D','21q_wpc-pVA',60),('E','GIceP3oLuDQ',124)]:
        r=by_id[key]
        assert int(r['seconds'])==seconds and r['playability']=='OK'
        assert sha(OUT/r['source_page'])==r['page_sha256']
        assert not any(r[f] for f in ['approved','media_downloaded','local_visual_review','local_audio_review'])
        selected.append(dict(label=label,**r))
    assert len(searches['candidates'])==len({r['id'] for r in searches['candidates']})
    result=dict(created_utc=datetime.now(timezone.utc).isoformat(),status='awaiting_user_media_review',
        user_rule='找到素材先给我审阅，我确认没问题你再download在本地做数据清洗',
        unique_search_entries=len(searches['candidates']),selected=selected,
        files={p.relative_to(ROOT).as_posix():sha(p) for p in OUT.glob('*') if p.is_file()},
        proposal_sha256=sha(ROOT/'research/补充标定素材候选V1.md'),
        implementation_unchanged=True,goal_status='active')
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(selected=[r['url'] for r in selected],unique_entries=result['unique_search_entries'],
        status=result['status'],media_files_downloaded=0),ensure_ascii=False))
if __name__=='__main__':main()

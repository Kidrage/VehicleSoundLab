"""Generate a fixed, two-way listening page from checked C render outputs."""
import json
from runtime_review import ROOT, sha

OUT=ROOT/'renders/gain_bridge_v1'


def main():
    if (OUT/'verification.json').exists() or (ROOT/'baselines/gain_bridge_v1').exists():
        raise SystemExit('Preserve frozen gain bridge review.')
    result=json.loads((OUT/'results.json').read_text())
    template=ROOT/'tools/gain_bridge_page.html';page=ROOT/'research/持续声层过渡试听V1.html'
    text=template.read_text(encoding='utf-8')
    for key,data in [('DATA',result['page_data']),('METHODS',result['methods'])]:
        text=text.replace('__'+key+'__',json.dumps(data,ensure_ascii=False).replace('</','<\\/'))
    page.write_text(text,encoding='utf-8')
    record=dict(result='pass',page=page.relative_to(ROOT).as_posix(),page_sha256=sha(page),
        base_results_sha256=sha(OUT/'results.json'),sources={p.relative_to(ROOT).as_posix():sha(p) for p in
        [template,ROOT/'tools/seekable_review_player_v1.js',ROOT/'tools/make_gain_bridge_page.py']})
    (OUT/'page.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    print(json.dumps(record,indent=2))


if __name__=='__main__':
    main()

"""YouTube public metadata only. New media still requires user review."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import re
import shutil
import urllib.request
from urllib.parse import urlencode


def label(v):
    if not isinstance(v,dict):return ''
    return v.get('simpleText','') or ''.join(x.get('text','') for x in v.get('runs',[]))


def rows(node):
    if isinstance(node,dict):
        if 'videoRenderer' in node:
            v=node['videoRenderer'];identity=v.get('videoId')
            if identity:yield dict(id=identity,title=label(v.get('title')),channel=label(v.get('ownerText')),
                duration=label(v.get('lengthText')),url='https://www.youtube.com/watch?v='+identity)
        for value in node.values():yield from rows(value)
    elif isinstance(node,list):
        for value in node:yield from rows(value)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    a=parser.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    def fetch(query):
        name,text=query;url='https://www.youtube.com/results?'+urlencode(dict(search_query=text))
        result=dict(query=text,url=url,media_downloaded=False,approved=False)
        try:
            request=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Accept-Language':'en-US,en;q=0.9'})
            with urllib.request.urlopen(request,timeout=25) as response:raw=response.read(12_000_000).decode('utf-8')
            (a.output/(name+'.html')).write_text(raw,encoding='utf-8')
            found=re.search(r'(?:var\s+)?ytInitialData\s*=\s*',raw)
            if not found:raise ValueError('No public search metadata')
            data=json.JSONDecoder().raw_decode(raw[found.end():])[0];seen=set();videos=[]
            for item in rows(data):
                if item['id'] not in seen:videos.append(item);seen.add(item['id'])
            result.update(status='metadata_only',candidates=videos)
        except Exception as exc:result.update(status='failed',error=repr(exc))
        return name,result
    queries=[('start','Lamborghini Huracan cold start exhaust pure sound'),
             ('pops','Lamborghini Huracan exhaust pops deceleration stock sound')]
    with ThreadPoolExecutor(max_workers=2) as pool:report=dict(pool.map(fetch,queries))
    (a.output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    shutil.copy2(__file__,a.output/'executed_search.py')
    for name,row in report.items():print(json.dumps(dict(key=name,**row),ensure_ascii=True),flush=True)


if __name__=='__main__':main()

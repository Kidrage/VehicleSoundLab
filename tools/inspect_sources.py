import html
import json
import re
import sys
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')

root = Path(__file__).resolve().parents[1]
tree = root / 'research/repository_tree.json'
if tree.exists() and '--tree' in sys.argv:
    data = json.loads(tree.read_text(encoding='utf-8'))
    for item in data.get('tree', []):
        print(item['path'], item.get('size', ''))
for name in ('search_papers_bing.html',):
    path = root / 'research' / name
    if not path.exists():
        continue
    source = path.read_text(encoding='utf-8')
    print('\nSEARCH', name)
    for block in re.findall(r'<li class="b_algo".*?</li>', source, re.S):
        print(html.unescape(re.sub('<[^>]+>', ' ', block))[:1800])
        print(re.findall(r'href="([^"]+)"', block)[:6])
for name in ('ioniq_history.json','ioniq_dna_history.json'):
    path=root/'research'/name
    if path.exists():
        print(name)
        for item in json.loads(path.read_text(encoding='utf-8')):
            print(item['sha'],item['commit']['message'],item['commit']['committer']['date'])

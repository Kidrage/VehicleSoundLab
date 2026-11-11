"""File-instance references only: dependency-cache entries are not DSP instances."""
import json
from pathlib import Path
import re


def boxes(patcher, prefix=()):
    for item in patcher.get('boxes', []):
        box = item['box']
        location = prefix+(box['id'],)
        yield location, box
        if 'patcher' in box:
            yield from boxes(box['patcher'], location)


def inspect(root):
    paths = sorted(p for p in root.rglob('*') if p.suffix in ('.maxpat','.gendsp'))
    names = {p.stem:p.relative_to(root).as_posix() for p in paths}
    assert len(names) == len(paths)
    edges, sample_reads, buffers, code_operators, dynamic = [], [], [], [], []
    documents = {}
    for path in paths:
        name = path.relative_to(root).as_posix()
        document = json.loads(path.read_text(encoding='utf-8-sig'))
        documents[name] = document
        for location, box in boxes(document['patcher']):
            cls, text = box['maxclass'], box.get('text','')
            if cls == 'comment':
                continue
            words = text.split()
            token = words[0] if words else ''
            ref = None
            kind = 'abstraction'
            if cls == 'bpatcher':
                ref = Path(box.get('name','').replace('Patcher:/','')).stem
                kind = 'bpatcher'
            elif cls == 'newobj' and token in names:
                ref = token
            elif cls == 'newobj' and token in ('poly~','pfft~') and len(words)>1:
                ref = Path(words[1]).stem
                kind = token
            if ref in names:
                edges.append(dict(source=name,node='/'.join(location),target=names[ref],kind=kind))
            for literal in re.findall(r'(?:Patcher:/)?([\w/.-]+\.(?:maxpat|gendsp))',text):
                target = names.get(Path(literal).stem)
                if target:
                    edges.append(dict(source=name,node='/'.join(location),target=target,kind='literal reference'))
            if cls == 'newobj' and token in ('groove~','play~','sfplay~','sfread~','index~','wave~','lookup~'):
                sample_reads.append(dict(path=name,node='/'.join(location),text=text))
            if cls == 'newobj' and token == 'buffer~':
                buffers.append(dict(path=name,node='/'.join(location),text=text))
            code = box.get('code','')
            if code:
                operators = sorted(set(re.findall(r'\b(?:noise|cycle|phasor|peek|sample|interp|delay|Buffer|Data)\b',code)))
                code_operators.append(dict(path=name,node='/'.join(location),operators=operators))
            if re.search(r'\bscript\s+(?:new|replace)|\bnewdefault\b',text):
                dynamic.append(dict(path=name,node='/'.join(location),text=text))
    for path in sorted((root/'code').glob('*.js')):
        for number,line in enumerate(path.read_text(encoding='utf-8-sig').splitlines(),1):
            if re.search(r'\.newdefault\b|\.newobject\b|\.newbpatcher\b',line):
                dynamic.append(dict(path=path.relative_to(root).as_posix(),line=number,text=line))
    return dict(edges=edges,sample_read_candidates=sample_reads,buffers=buffers,
                gen_code_operators=code_operators,dynamic_construction=dynamic), documents


def reachable(edges, root):
    seen, pending = set(), [root]
    while pending:
        source = pending.pop()
        if source in seen:
            continue
        seen.add(source)
        pending += [e['target'] for e in edges if e['source'] == source]
    return sorted(seen)

"""Small shared archive primitives; per-study evidence assertions stay separate."""
import csv,hashlib,io,json,shutil,zipfile
from pathlib import Path


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def load(path):return json.loads(Path(path).read_text(encoding='utf-8'))


def save(path,obj):
    Path(path).write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')


def freeze(root,repo,sources,evidence,inputs,validation):
    root=Path(root);repo=Path(repo);root.mkdir(parents=True,exist_ok=False)
    shutil.copytree(evidence,root/'evidence')
    for name in sorted(set(sources)):
        path=repo/name
        assert path.resolve().is_relative_to(repo.resolve())
        dest=root/'source'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,dest)
    for name,path in inputs.items():
        dest=root/'inputs'/name
        assert dest.resolve().is_relative_to((root/'inputs').resolve())
        dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,dest)
    with zipfile.ZipFile(root/'source.zip','w',compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted((root/'source').rglob('*')):
            if path.is_file():archive.write(path,path.relative_to(root/'source').as_posix())
    save(root/'validation.json',validation)
    entries=[dict(path=p.relative_to(root).as_posix(),bytes=p.stat().st_size,sha256=sha(p))
        for p in sorted(root.rglob('*')) if p.is_file()]
    manifest=dict(files=entries,file_count=len(entries),bytes=sum(x['bytes'] for x in entries))
    save(root/'manifest.json',manifest)
    return dict(manifest_sha256=sha(root/'manifest.json'),file_count=manifest['file_count'],bytes=manifest['bytes'])


def verify(root):
    root=Path(root);manifest=load(root/'manifest.json');expected={row['path'] for row in manifest['files']}
    actual={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and p!=root/'manifest.json'}
    assert expected==actual and len(expected)==manifest['file_count']
    for row in manifest['files']:
        path=root/row['path'];assert path.resolve().is_relative_to(root.resolve())
        assert path.stat().st_size==row['bytes'] and sha(path)==row['sha256'],row['path']
    return manifest


def append_index(path,row):
    assert len(row)==8
    path=Path(path);before=path.read_bytes()
    rows=list(csv.reader(io.StringIO(before.decode('utf-8-sig'))))
    assert all(len(value)==8 for value in rows) and all(value[0]!=row[0] for value in rows)
    buffer=io.StringIO(newline='');csv.writer(buffer,lineterminator='\n').writerow(row)
    path.write_bytes(before+(b'' if before.endswith(b'\n') else b'\n')+buffer.getvalue().encode('utf-8'))

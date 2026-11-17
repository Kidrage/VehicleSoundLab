"""Historical voices-only identity; catalog_assets covers the complete catalog."""
import hashlib
from pathlib import Path


def voices(repo):
    root=Path(repo)/'voices';rows=[]
    for path in sorted(root.rglob('*')):
        if path.is_file():rows.append((path.relative_to(root).as_posix(),hashlib.sha256(path.read_bytes()).hexdigest()))
    if not rows:raise RuntimeError('声源参数库为空')
    digest=hashlib.sha256()
    for name,value in rows:digest.update((name+'\0'+value+'\n').encode('utf-8'))
    return digest.hexdigest(),rows

"""Versioned ZIP64 packaging with a per-file SHA-256 ledger and readback check."""
from pathlib import Path
import argparse
import hashlib
import json
import zipfile

ROOT=Path(__file__).resolve().parents[2]
MANIFEST='handoff/archive-manifest.json'
BLOCK=2**20
LIMIT=4*2**30


def digest(file):
    with file.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def files_at(folder):
    return sorted(p for p in folder.rglob('*') if p.is_file() and not p.is_symlink() and '__pycache__' not in p.parts and p.suffix!='.pyc')


def split(files):
    group=[];size=0
    for p in files:
        n=p.stat().st_size
        if group and size+n>LIMIT:
            yield group;group=[];size=0
        group.append(p);size+=n
    if group:yield group


def frozen_expectations():
    manifests=sorted((ROOT/'baselines').glob('*/manifest.json'))
    latest=ROOT/'baselines/low_rumble_v2'
    prior=json.loads((latest/'references/analysis/low_rumble_v2/audit.json').read_text(encoding='utf-8'))['old_snapshot_manifests']
    prior[latest.name]=digest(latest/'manifest.json')
    assert set(prior)=={p.parent.name for p in manifests}
    required={}
    for p in manifests:
        assert digest(p)==prior[p.parent.name],p
        rows=json.loads(p.read_text(encoding='utf-8-sig'))['files']
        for row in rows:
            path=p.parent/row['path'];required[path.relative_to(ROOT).as_posix()]=row['sha256']
    assert len(manifests)==48 and len(required)==6360
    return required


def make_zip(source,files,dest,expected=None):
    tmp=dest.with_suffix('.partial')
    if dest.exists() or tmp.exists():raise FileExistsError(dest)
    rows=[];names=set();expected=expected or {}
    with zipfile.ZipFile(tmp,'x',allowZip64=True) as archive:
        for p in files:
            name=p.relative_to(source).as_posix();assert name.casefold() not in names and name!=MANIFEST,p
            names.add(name.casefold());before=p.stat();info=zipfile.ZipInfo.from_file(p,name)
            if p.suffix.lower() in {'.json','.csv','.txt','.md','.c','.h','.html','.js','.py','.svg','.xml','.maxpat','.gendsp','.ini'}:
                info.compress_type=zipfile.ZIP_DEFLATED;info._compresslevel=1
            sha=hashlib.sha256();total=0
            with p.open('rb') as stream,archive.open(info,'w',force_zip64=before.st_size>=2**31) as target:
                while block:=stream.read(BLOCK):
                    sha.update(block);target.write(block);total+=len(block)
            after=p.stat();identity=sha.hexdigest()
            assert total==before.st_size==after.st_size and before.st_mtime_ns==after.st_mtime_ns,p
            if name in expected:assert identity==expected[name],p
            rows.append(dict(path=name,bytes=total,sha256=identity))
        archive.writestr(MANIFEST,json.dumps(dict(schema='vsl.archive/1',files=rows),ensure_ascii=False,indent=2),compress_type=zipfile.ZIP_DEFLATED)
    # Reading each entire entry also exercises ZIP CRC, and detects truncation.
    with zipfile.ZipFile(tmp) as archive:
        assert len(archive.infolist())==len(rows)+1
        for row in rows:
            with archive.open(row['path']) as stream:assert hashlib.file_digest(stream,'sha256').hexdigest()==row['sha256'],row['path']
    identity=digest(tmp);tmp.rename(dest)
    result=dict(file=dest.name,files=len(rows),bytes=dest.stat().st_size,sha256=identity,all_payload_sha256_verified=True)
    print(json.dumps(result),flush=True);return result


def main():
    parser=argparse.ArgumentParser();parser.add_argument('destination',type=Path);args=parser.parse_args()
    dest=args.destination.resolve();dest.mkdir(parents=True,exist_ok=True)
    receipt=dest/'evidence-index.json'
    if receipt.exists():raise FileExistsError(receipt)
    expected=frozen_expectations();packed=[];present=set()
    groups=[('02-history','baselines'),('03-references','references'),('04-renders','renders'),('05-analysis-dependencies','tools/python_deps')]
    for label,folder in groups:
        files=files_at(ROOT/folder);assert files,folder
        present.update(p.relative_to(ROOT).as_posix() for p in files)
        parts=list(split(files))
        for i,part in enumerate(parts,1):
            name=label+('-'+str(i).zfill(2) if len(parts)>1 else '')+'.zip'
            packed.append(make_zip(ROOT,part,dest/name,expected))
    assert expected.keys()<=present
    receipt.write_text(json.dumps(dict(schema='vsl.handoff-evidence/1',date='2026-11-11',old_snapshots=48,
        frozen_files_verified=6360,parts=packed),ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':main()

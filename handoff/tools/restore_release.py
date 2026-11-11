"""Verify and join release ZIP parts. Python 3.11+, no third-party dependencies."""
import argparse
import hashlib
import json
from pathlib import Path

BLOCK=4*2**20


def safe_name(name):
    if Path(name).name != name or "/" in name or "\\" in name or ":" in name:
        raise ValueError(f"Unsafe filename: {name}")
    return name


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream,"sha256").hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory",type=Path,nargs="?",default=Path("."))
    parser.add_argument("--verify-only",action="store_true")
    args=parser.parse_args()
    root=args.directory.resolve()
    manifest=json.loads((root/"release-manifest.json").read_text(encoding="utf-8"))
    if manifest["schema"]!="vsl.release/1":
        raise ValueError("Unsupported release manifest")
    for archive in manifest["archives"]:
        output=root/safe_name(archive["name"])
        aggregate=hashlib.sha256()
        size=0
        parts=[]
        for row in archive["parts"]:
            part=root/safe_name(row["name"])
            if part.stat().st_size!=row["bytes"]:
                raise ValueError(f"Size mismatch: {part}")
            part_hash=hashlib.sha256()
            with part.open("rb") as stream:
                while block:=stream.read(BLOCK):
                    part_hash.update(block)
                    aggregate.update(block)
                    size+=len(block)
            if part_hash.hexdigest()!=row["sha256"]:
                raise ValueError(f"SHA-256 mismatch: {part}")
            parts.append(part)
        if aggregate.hexdigest()!=archive["sha256"] or size!=archive["bytes"]:
            raise ValueError(f"Reassembled ZIP mismatch: {archive['name']}")
        if output.exists():
            if output.stat().st_size!=size or digest(output)!=archive["sha256"]:
                raise FileExistsError(f"Conflicting existing file: {output}")
            print(f"{output.name}: verified; ZIP already present",flush=True)
        elif args.verify_only:
            print(f"{output.name}: all parts and combined hash verified",flush=True)
        else:
            temporary=output.with_suffix(output.suffix+".joining")
            with temporary.open("xb") as target:
                for part in parts:
                    with part.open("rb") as source:
                        while block:=source.read(BLOCK):
                            target.write(block)
            if digest(temporary)!=archive["sha256"]:
                raise ValueError(f"Joined ZIP hash mismatch: {temporary}")
            temporary.rename(output)
            print(f"{output.name}: joined and verified",flush=True)


if __name__=="__main__":
    main()

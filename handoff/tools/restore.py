"""Restore selected VSL archives over one project; standard-library Python 3.11+."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
from tempfile import NamedTemporaryFile
import zipfile

MANIFEST = "handoff/archive-manifest.json"


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def target(root, name):
    parts = name.split("/")
    if any(not p or p in {".",".."} or p.endswith((".", " ")) or
           re.search(r'[\\:<>"|?*\x00-\x1f]', p) or
           re.fullmatch(r"(?:con|prn|aux|nul|com[1-9¹²³]|lpt[1-9¹²³])", p.split(".")[0], re.I)
           for p in parts):
        raise ValueError(f"Unsafe path: {name}")
    path = root.joinpath(*PurePosixPath(name).parts)
    if path.resolve() != path:
        raise ValueError(f"Unexpected link: {path}")
    return path


def restore(archive_path, root):
    with zipfile.ZipFile(archive_path) as archive:
        listing = archive.namelist()
        if len({n.casefold() for n in listing}) != len(listing):
            raise ValueError("Duplicate ZIP paths")
        manifest = json.loads(archive.read(MANIFEST))
        if manifest["schema"] != "vsl.archive/1":
            raise ValueError("Unsupported manifest")
        rows = manifest["files"]
        if len(listing) != len(rows)+1 or set(listing) != {r["path"] for r in rows}|{MANIFEST}:
            raise ValueError("Manifest/ZIP mismatch")
        missing = []
        for row in rows:
            name = row["path"]
            dest = target(root, name)
            if archive.getinfo(name).file_size != row["bytes"]:
                raise ValueError(f"Size mismatch: {name}")
            if dest.exists():
                if not dest.is_file() or dest.stat().st_size != row["bytes"] or digest(dest) != row["sha256"]:
                    raise FileExistsError(f"Conflicting file (kept): {dest}")
            else:
                missing.append((row, dest))
        for row, dest in missing:
            dest.parent.mkdir(parents=True, exist_ok=True)
            with NamedTemporaryFile(dir=dest.parent, prefix=".vsl-restore-", delete=False) as temp:
                staging = Path(temp.name)
                try:
                    with archive.open(row["path"]) as source:
                        shutil.copyfileobj(source, temp, 2**20)
                    temp.close()
                    if digest(staging) != row["sha256"]:
                        raise ValueError(f"SHA-256 mismatch: {row['path']}")
                    if os.name == "nt":
                        staging.rename(dest)  # Windows rename fails when destination exists.
                    else:
                        os.link(staging, dest)
                finally:
                    temp.close()
                    staging.unlink(missing_ok=True)
    print(f"{archive_path.name}: {len(missing)} restored, {len(rows)-len(missing)} identical", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    parser.add_argument("archives", type=Path, nargs="+")
    args = parser.parse_args()
    root = args.project.resolve()
    root.mkdir(parents=True, exist_ok=True)
    for p in args.archives:
        restore(p, root)


if __name__ == "__main__":
    main()


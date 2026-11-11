"""Split original handoff ZIPs below GitHub's 2 GiB asset limit; retain byte identity."""
import argparse
import hashlib
import json
import os
from pathlib import Path

CHUNK_LIMIT = 2040 * 2**20
BLOCK = 4 * 2**20


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def safe_name(name):
    if Path(name).name != name or "/" in name or "\\" in name or ":" in name:
        raise ValueError(name)
    return name


def prepare(source, destination):
    source, destination = source.resolve(), destination.resolve()
    destination.mkdir(exist_ok=True)
    manifest = destination/"release-manifest.json"
    package = json.loads((source/"package-index.json").read_text(encoding="utf-8"))
    archives = []
    for row in package["parts"]:
        path = source/safe_name(row["file"])
        if path.stat().st_size != row["bytes"]:
            raise ValueError(f"Archive size changed: {path}")
        parts, aggregate = [], hashlib.sha256()
        with path.open("rb") as original:
            index = 0
            while remaining := row["bytes"] - original.tell():
                index += 1
                count = min(CHUNK_LIMIT, remaining)
                name = path.name if row["bytes"] <= CHUNK_LIMIT else f"{path.name}.part{index:02d}"
                output = destination/name
                if output.exists():
                    if output.stat().st_size != count:
                        raise ValueError(f"Existing part size mismatch: {output}")
                    part_hash = hashlib.sha256()
                    with output.open("rb") as saved:
                        consumed = 0
                        while block := saved.read(BLOCK):
                            if original.read(len(block)) != block:
                                raise ValueError(f"Existing part differs: {output}")
                            aggregate.update(block)
                            part_hash.update(block)
                            consumed += len(block)
                    if consumed != count:
                        raise ValueError(output)
                elif name == path.name:
                    os.link(path, output)
                    part_hash = hashlib.sha256()
                    while block := original.read(BLOCK):
                        aggregate.update(block)
                        part_hash.update(block)
                else:
                    temporary = output.with_suffix(output.suffix+".partial")
                    part_hash = hashlib.sha256()
                    with temporary.open("xb") as target:
                        left = count
                        while left:
                            block = original.read(min(BLOCK,left))
                            if not block:
                                raise EOFError(path)
                            target.write(block)
                            aggregate.update(block)
                            part_hash.update(block)
                            left -= len(block)
                    temporary.rename(output)
                    if sha(output) != part_hash.hexdigest():
                        raise ValueError(f"Written part hash mismatch: {output}")
                parts.append({"name":name,"bytes":count,"sha256":part_hash.hexdigest()})
                print(json.dumps({"prepared":name,"bytes":count}),flush=True)
        if aggregate.hexdigest() != row["sha256"]:
            raise ValueError(f"Original ZIP hash mismatch: {path}")
        archives.append({"name":path.name,"bytes":row["bytes"],"sha256":row["sha256"],"parts":parts})
    result={"schema":"vsl.release/1","date":"2026-11-11","tag":"handoff-2026-11-11",
            "repository":"Kidrage/VehicleSoundLab","original_package_index":"package-index.json","archives":archives}
    temporary=manifest.with_suffix(".json.partial")
    temporary.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    temporary.replace(manifest)
    (destination/"SHA256SUMS-release.txt").write_text("".join(
        f'{part["sha256"]}  {part["name"]}\n' for archive in archives for part in archive["parts"]),encoding="ascii")
    print(json.dumps({"archives":len(archives),"upload_assets":sum(len(a["parts"]) for a in archives),
                      "total_bytes":sum(a["bytes"] for a in archives)}),flush=True)


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source",type=Path)
    parser.add_argument("destination",type=Path)
    args=parser.parse_args()
    prepare(args.source,args.destination)

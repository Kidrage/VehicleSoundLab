"""Upload verified handoff assets, then publish the Release after server digest checks."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

REPO="Kidrage/VehicleSoundLab"
TAG="handoff-2026-11-11"


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream,"sha256").hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory",type=Path)
    parser.add_argument("--gh",default="gh")
    parser.add_argument("--report",type=Path,required=True)
    args=parser.parse_args()
    root=args.directory.resolve()
    env=os.environ.copy()
    env["GH_PROMPT_DISABLED"]="1"
    env["GODEBUG"]="http2client=0"

    def gh(*arguments,check=True):
        result=subprocess.run([args.gh,*arguments],capture_output=True,text=True,env=env,timeout=10800,encoding="utf-8")
        if check and result.returncode:
            raise RuntimeError(result.stderr.strip() or "GitHub CLI command failed")
        return result

    def api(endpoint):
        return json.loads(gh("api",endpoint).stdout)

    user=api("user")
    print(json.dumps({"authenticated_as":user["login"]}),flush=True)
    source=json.loads((root/"asset-manifest.json").read_text(encoding="utf-8"))
    expected={r["name"]:r for r in source["assets"]}
    expected["asset-manifest.json"]={"name":"asset-manifest.json","bytes":(root/"asset-manifest.json").stat().st_size,
                                     "sha256":digest(root/"asset-manifest.json")}
    for name,row in expected.items():
        p=root/name
        if p.stat().st_size!=row["bytes"] or digest(p)!=row["sha256"]:
            raise ValueError(f"Local asset identity changed: {name}")
    release_result=gh("api",f"repos/{REPO}/releases/tags/{TAG}",check=False)
    if release_result.returncode:
        if "404" not in release_result.stderr:
            raise RuntimeError(release_result.stderr)
        gh("release","create",TAG,"--repo",REPO,"--draft","--target","main",
           "--title","Vehicle Sound Lab · 完整工程交接 2026-11-11",
           "--notes-file",str(root/"RELEASE-NOTES.md"))
        release=json.loads(gh("api",f"repos/{REPO}/releases/tags/{TAG}").stdout)
    else:
        release=json.loads(release_result.stdout)
    release_id=release["id"]

    def list_assets():
        return api(f"repos/{REPO}/releases/{release_id}/assets?per_page=100")

    def matches(asset,row):
        return asset["state"]=="uploaded" and asset["size"]==row["bytes"] and asset.get("digest")=="sha256:"+row["sha256"]

    existing={a["name"]:a for a in list_assets()}
    pending=[]
    for name,row in expected.items():
        asset=existing.get(name)
        if asset and matches(asset,row):
            print(json.dumps({"verified_existing":name}),flush=True)
        else:
            if not release["draft"]:
                raise RuntimeError("Published release differs; preserve it for review")
            if asset:
                gh("api","--method","DELETE",f"repos/{REPO}/releases/assets/{asset['id']}")
            pending.append(row)

    def upload(row):
        name=row["name"]
        for attempt in range(1,4):
            print(json.dumps({"uploading":name,"bytes":row["bytes"],"attempt":attempt}),flush=True)
            result=gh("release","upload",TAG,str(root/name),"--repo",REPO,check=False)
            uploaded=next((a for a in list_assets() if a["name"]==name),None)
            if uploaded and matches(uploaded,row):
                print(json.dumps({"server_sha256_verified":name}),flush=True)
                return
            if uploaded:
                gh("api","--method","DELETE",f"repos/{REPO}/releases/assets/{uploaded['id']}")
            if attempt==3:
                raise RuntimeError(f"Upload not verified: {name}: {result.stderr}")
            time.sleep(5*attempt)

    # Send the smallest assets first so instructions and one complete system ZIP are available early.
    pending.sort(key=lambda row:row["bytes"])
    failures=[]
    with ThreadPoolExecutor(max_workers=2) as pool:
        for future in as_completed([pool.submit(upload,row) for row in pending]):
            try:
                future.result()
            except Exception as error:
                failures.append(str(error))
    if failures:
        raise RuntimeError("; ".join(failures))
    assets={a["name"]:a for a in list_assets()}
    verified=[]
    for name,row in expected.items():
        asset=assets[name]
        if not matches(asset,row):
            raise ValueError(f"Remote identity mismatch: {name}")
        verified.append({"name":name,"bytes":row["bytes"],"sha256":row["sha256"],
                         "server_digest":asset["digest"],"url":asset["browser_download_url"]})
    gh("release","edit",TAG,"--repo",REPO,"--draft=false")
    final=api(f"repos/{REPO}/releases/{release_id}")
    if final["draft"]:
        raise ValueError("Release remains a draft")
    report={"schema":"vsl.release-upload/1","url":final["html_url"],"tag":TAG,
            "all_server_sha256_verified":True,"assets":verified}
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"published":final["html_url"],"assets":len(verified),
                      "bytes":sum(r["bytes"] for r in verified),"all_server_sha256_verified":True}),flush=True)


if __name__=="__main__":
    main()

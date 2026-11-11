"""Upload handoff attachments with streaming progress and verify GitHub's SHA-256 digests."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import http.client
import json
import os
from pathlib import Path
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

REPO="Kidrage/VehicleSoundLab"
TAG="handoff-2026-11-11"
BLOCK=2**20

def log(**row):
    print(json.dumps(row,ensure_ascii=True),flush=True)

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
    token_result=subprocess.run([args.gh,"auth","token","--hostname","github.com"],
                                text=True,capture_output=True,timeout=20)
    if token_result.returncode:
        raise RuntimeError("GitHub CLI credential unavailable")
    token=token_result.stdout.strip()
    headers={"Authorization":"Bearer "+token,"Accept":"application/vnd.github+json",
             "X-GitHub-Api-Version":"2022-11-28","User-Agent":"VehicleSoundLab-handoff",
             "Cache-Control":"no-cache, no-store"}
    def api(endpoint,method="GET",body=None):
        encoded=json.dumps(body).encode() if body is not None else None
        for attempt in range(1,6):
            url="https://api.github.com/"+endpoint
            url+=("&" if "?" in url else "?")+"vsl_request="+uuid.uuid4().hex
            request=urllib.request.Request(url,data=encoded,headers={**headers,"Content-Type":"application/json"},method=method)
            try:
                with urllib.request.urlopen(request,timeout=45) as response:
                    return json.load(response) if response.status!=204 else None
            except urllib.error.HTTPError as error:
                if error.code<500 and error.code!=429:
                    raise
            except (OSError,http.client.HTTPException):
                pass
            log(api_retry=endpoint,attempt=attempt)
            if attempt==5:
                raise RuntimeError("GitHub API transport failed: "+endpoint)
            time.sleep(2*attempt)
    user=api("user")
    log(authenticated_as=user["login"])
    source=json.loads((root/"asset-manifest.json").read_text(encoding="utf-8"))
    expected={r["name"]:r for r in source["assets"]}
    expected["asset-manifest.json"]={"name":"asset-manifest.json","bytes":(root/"asset-manifest.json").stat().st_size,
                                     "sha256":digest(root/"asset-manifest.json")}
    for name,row in expected.items():
        path=root/name
        if Path(name).name!=name or path.stat().st_size!=row["bytes"] or digest(path)!=row["sha256"]:
            raise ValueError("Local asset identity changed: "+name)
    log(local_assets_verified=len(expected))
    try:
        release=api(f"repos/{REPO}/releases/tags/{TAG}")
    except urllib.error.HTTPError as error:
        if error.code!=404:
            raise
        payload={"tag_name":TAG,"target_commitish":"main","name":"Vehicle Sound Lab · 完整工程交接 2026-11-11",
                 "body":(root/"RELEASE-NOTES.md").read_text(encoding="utf-8"),"draft":True,"prerelease":False}
        release=api(f"repos/{REPO}/releases",method="POST",body=payload)
    release_id=release["id"]
    upload_url=release["upload_url"].split("{",1)[0]
    log(release_draft=release["draft"],release_id=release_id)
    def list_assets():
        return api(f"repos/{REPO}/releases/{release_id}/assets?per_page=100")
    def matches(asset,row):
        return (asset["state"]=="uploaded" and asset["size"]==row["bytes"]
                and asset.get("digest")=="sha256:"+row["sha256"])
    existing={a["name"]:a for a in list_assets()}
    pending=[]
    for name,row in expected.items():
        asset=existing.get(name)
        if asset and matches(asset,row):
            log(verified_existing=name)
        else:
            if not release["draft"]:
                raise RuntimeError("Published release differs; preserve it for review")
            if asset:
                api(f"repos/{REPO}/releases/assets/{asset['id']}",method="DELETE")
            pending.append(row)

    def send_file(row):
        url=urllib.parse.urlsplit(upload_url)
        if url.scheme!="https" or url.hostname!="uploads.github.com":
            raise ValueError("Unexpected upload origin")
        query=urllib.parse.urlencode({"name":row["name"],"vsl_request":uuid.uuid4().hex})
        connection=http.client.HTTPSConnection(url.hostname,timeout=90)
        try:
            connection.putrequest("POST",url.path+"?"+query)
            for key,value in headers.items():
                connection.putheader(key,value)
            connection.putheader("Content-Type","application/octet-stream")
            connection.putheader("Content-Length",str(row["bytes"]))
            connection.endheaders()
            sent=0
            started=last=time.monotonic()
            with (root/row["name"]).open("rb") as stream:
                while block:=stream.read(BLOCK):
                    connection.send(block)
                    sent+=len(block)
                    now=time.monotonic()
                    if now-last>=12:
                        log(progress=row["name"],sent=sent,total=row["bytes"],
                            mib_per_second=round(sent/2**20/max(1,now-started),2))
                        last=now
            response=connection.getresponse()
            payload=response.read()
            if response.status!=201:
                raise RuntimeError("Upload HTTP "+str(response.status))
            result=json.loads(payload)
            if not matches(result,row):
                raise ValueError("Upload digest mismatch: "+row["name"])
            return result
        finally:
            connection.close()

    def upload(row):
        for attempt in range(1,4):
            log(uploading=row["name"],bytes=row["bytes"],attempt=attempt)
            try:
                result=send_file(row)
                log(server_sha256_verified=row["name"],url=result["browser_download_url"])
                return
            except Exception as error:
                log(upload_retry=row["name"],error_type=type(error).__name__,reason=str(error),attempt=attempt)
                asset=next((a for a in list_assets() if a["name"]==row["name"]),None)
                if asset and matches(asset,row):
                    log(server_sha256_verified=row["name"])
                    return
                if asset:
                    api(f"repos/{REPO}/releases/assets/{asset['id']}",method="DELETE")
                if attempt==3:
                    raise
                time.sleep(5*attempt)
    pending.sort(key=lambda row:row["bytes"])
    failures=[]
    with ThreadPoolExecutor(max_workers=2) as pool:
        for future in as_completed([pool.submit(upload,row) for row in pending]):
            try:
                future.result()
            except Exception as error:
                failures.append(type(error).__name__+": "+str(error))
    if failures:
        raise RuntimeError("; ".join(failures))
    remote={a["name"]:a for a in list_assets()}
    verified=[]
    for name,row in expected.items():
        asset=remote[name]
        if not matches(asset,row):
            raise ValueError("Remote identity mismatch: "+name)
        verified.append({**row,"server_digest":asset["digest"],"url":asset["browser_download_url"]})
    final=api(f"repos/{REPO}/releases/{release_id}",method="PATCH",body={"draft":False})
    if final["draft"]:
        raise ValueError("Release remains a draft")
    report={"schema":"vsl.release-upload/1","url":final["html_url"],"tag":TAG,
            "all_server_sha256_verified":True,"assets":verified}
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    log(published=final["html_url"],assets=len(verified),bytes=sum(r["bytes"] for r in verified),
        all_server_sha256_verified=True)

if __name__=="__main__":
    main()

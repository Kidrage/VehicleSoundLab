"""Fetch a low-resolution silent track of approved A to label mic/camera context.
Uses the already obtained metadata from the approved extraction.
"""
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/python_deps'))
from yt_dlp import YoutubeDL
manifest=json.loads((ROOT/'references/approval_manifest.json').read_text(encoding='utf-8'))
assert next(v for v in manifest if v['id']=='A')['approved'] is True
with YoutubeDL(dict(format='134',proxy='http://127.0.0.1:7890',retries=1,socket_timeout=25,
    outtmpl=str(ROOT/'references/raw/A_context_360p.%(ext)s'),noplaylist=True)) as ydl:
    ydl.download_with_info_file(str(ROOT/'references/raw/A_7aZm1Wkp6QM.info.json'))

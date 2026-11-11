import json
import hashlib
import subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
path=ROOT/'references/raw/B_local_Tecnica_binaural.mp3'
source_hash=hashlib.sha256(path.read_bytes()).hexdigest()
manifest=ROOT/'references/approval_manifest.json'
items=json.loads(manifest.read_text(encoding='utf-8'))
item=next(v for v in items if v['id']=='B')
item.update(local_file=str(path),sha256=source_hash,
    approval_evidence=item['approval_evidence']+'; user supplied local desktop MP3 and explicitly requested relocation into workspace')
manifest.write_text(json.dumps(items,ensure_ascii=False,indent=2),encoding='utf-8')
provenance=dict(source_id='B',url=item['url'],origin='User-supplied local MP3; moved from Desktop after SHA256 verification',
    original_file=path.name,sha256=source_hash,sample_rate=48000,channels=2,duration_seconds=852.195563,
    codec='mp3',identity_note='Filename matches the approved video; no bit-exact comparison to a YouTube stream was possible.',
    approval_evidence=item['approval_evidence'])
(ROOT/'references/raw/B_provenance.json').write_text(json.dumps(provenance,indent=2,ensure_ascii=False),encoding='utf-8')
for identity,filename in [('A','A_7aZm1Wkp6QM.webm'),('B',path.name)]:
    output=ROOT/f'references/clean/{identity}_decoded_float.wav'
    if output.exists():continue
    command=['ffmpeg','-hide_banner','-nostdin','-n','-i',str(ROOT/'references/raw'/filename),
        '-vn','-map_metadata','-1','-c:a','pcm_f32le',str(output)]
    result=subprocess.run(command,capture_output=True,text=True)
    (ROOT/f'references/analysis/{identity}_decode_log.txt').write_text(result.stderr,encoding='utf-8')
    result.check_returncode()
    (output.with_suffix('.provenance.json')).write_text(json.dumps(dict(source=filename,sha256=hashlib.sha256((ROOT/'references/raw'/filename).read_bytes()).hexdigest(),
        command=command,processing='Float32 decode only; codec overshoots preserved; original rate/channels; no filtering or gain changes',
        decode_warning='Terminal Opus packet warning; tail excluded' if identity=='A' else None),indent=2),encoding='utf-8')
print('Both references decoded as float; raw media preserved. B SHA256',source_hash)

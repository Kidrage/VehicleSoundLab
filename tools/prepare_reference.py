"""Cut a user-approved LOCAL reference. Never downloads anything.

Approval manifest is populated only after explicit user confirmation.
The input remains untouched; no denoising, compression or normalization.
"""
import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('manifest',type=Path); p.add_argument('source_id'); p.add_argument('input',type=Path)
    p.add_argument('output',type=Path); p.add_argument('--start',type=float,required=True)
    p.add_argument('--duration',type=float,required=True); p.add_argument('--highpass',action='store_true')
    a=p.parse_args(); items=json.loads(a.manifest.read_text(encoding='utf-8'))
    item=next((v for v in items if v['id']==a.source_id),None)
    if not item or item.get('approved') is not True or not item.get('approval_evidence'):
        p.error('Reference has no explicit user approval recorded. Nothing processed.')
    if a.start<0 or a.duration<=0:p.error('Invalid time range')
    if a.input.resolve()==a.output.resolve() or a.output.exists():p.error('Output must be a new file')
    ffmpeg=shutil.which('ffmpeg')
    if not ffmpeg:p.error('ffmpeg required')
    # Fixed, reversible headroom prevents filter or codec overshoot from being
    # clipped by integer export. This is NOT per-clip peak normalization.
    filters=['volume=0.5','aresample=48000:resampler=swr:filter_size=64:phase_shift=10:cutoff=0.97']
    if a.highpass:filters.append('highpass=f=28')
    filters+=['afade=t=in:d=0.005',f'afade=t=out:st={max(0,a.duration-.005):.9f}:d=0.005']
    temporary=a.output.with_name(a.output.stem+'.partial.wav')
    command=[ffmpeg,'-hide_banner','-nostdin','-n','-ss',str(a.start),'-i',str(a.input),'-t',str(a.duration),
        '-vn','-map_metadata','-1','-af',','.join(filters),'-c:a','pcm_s24le',str(temporary)]
    subprocess.run(command,check=True)
    temporary.replace(a.output)
    report=dict(source_id=a.source_id,url=item['url'],approval_evidence=item['approval_evidence'],
        input_sha256=digest(a.input),output_sha256=digest(a.output),start=a.start,duration=a.duration,
        channels='preserved',fixed_analysis_gain_db=-6.020599913279624,
        highpass_hz=28 if a.highpass else None,
        denoise=False,normalization=False,command=command,
        ffmpeg_version=subprocess.check_output([ffmpeg,'-version'],text=True).splitlines()[0])
    a.output.with_suffix(a.output.suffix+'.provenance.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('Prepared approved reference with provenance:',a.output)

if __name__=='__main__':main()

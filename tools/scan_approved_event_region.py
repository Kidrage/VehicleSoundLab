"""Scan approved local 48 kHz media with fixed windows and both backgrounds."""
import argparse
import json
from pathlib import Path
import shutil
import sys


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', required=True)
    p.add_argument('--range', nargs=2, type=float, action='append', required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--detector', choices=('high', 'low_mid', 'short_high'), default='high')
    p.add_argument('--data-root', type=Path, default=Path('E:/VehicleSoundLab'))
    a = p.parse_args()
    sys.path.insert(0, str(a.data_root/'tools/python_deps'))
    from event_authoring.audio import sha
    from event_authoring.scan import scan_file
    repo = Path(__file__).resolve().parents[1]
    manifest = json.loads((repo/'references/segments_v1.json').read_text(encoding='utf-8'))
    approvals = json.loads((a.data_root/'references/approval_manifest.json').read_text(encoding='utf-8'))
    if not any(r['id'] == a.source and r['approved'] for r in approvals):
        raise ValueError('Local source must already be approved')
    spec = manifest['sources'][a.source]
    path = a.data_root/spec['master']
    if sha(path) != spec['master_sha256']:
        raise ValueError('Approved master identity changed')
    def progress(block):
        print(json.dumps(dict(seconds=block['retain_seconds'],candidates=len(block['candidates']))),flush=True)
    result=scan_file(path,a.range,progress,mode=a.detector)
    rows=[dict(source_id=a.source,**row) for row in result['candidates']]
    a.output.mkdir(parents=True, exist_ok=False)
    report = dict(schema='vsl.approved-event-region-scan/1', source_id=a.source,
                  source=str(path), source_sha256=spec['master_sha256'], requested_ranges=a.range,
                  detector=result['detector'], block_context_seconds=.5, blocks=result['blocks'], candidates=rows,
                  limits=['Full-band contrast does not identify a physical event.',
                          'Fixed 30 s block peak selection can differ within 100 ms of a block boundary.',
                          'No background search, source separation, cleaning, fitting, label inference or new download.'])
    (a.output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    exact=a.output/'exact_sources';exact.mkdir()
    for source in [Path(__file__), repo/'tools/event_authoring/scan.py',repo/'tools/event_authoring/audio.py']:
        shutil.copy2(source,exact/source.name)
    shortlist=sorted(rows,key=lambda r:r['minimum_contrast_db'],reverse=True)[:16]
    print(json.dumps(dict(total=len(rows),both_above_3db=sum(r['both_full_band_above_3db'] for r in rows),
                         ranked=[{k:r[k] for k in ('source_seconds','minimum_contrast_db','contrast_db')} for r in shortlist]),ensure_ascii=False),flush=True)


if __name__ == '__main__':main()

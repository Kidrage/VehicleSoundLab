"""Independently read the frozen bytes, telemetry, raw reference and six bands."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import urllib.request

import numpy as np
import soundfile as sf


def checksum(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1048576),b''):h.update(block)
    return h.hexdigest()


def load(path):return json.loads(Path(path).read_text(encoding='utf-8'))


def bands(x):
    window=np.hanning(2049)[:-1]
    parts=[]
    for first in range(0,len(x)-2048+1,1024):
        z=np.fft.rfft(x[first:first+2048]*window[:,None],axis=0)
        p=(z.real*z.real+z.imag*z.imag)/(48000*np.sum(window*window))
        p[1:-1]*=2;parts.append(p)
    psd=np.mean(parts,axis=0);f=np.arange(1025)*(48000/2048)
    return np.array([psd[(f>=lo)&((f<hi) if hi<24000 else (f<=hi))].sum(axis=0)*(48000/2048)
        for lo,hi in zip((0,60,300,1200,4500,14000),(60,300,1200,4500,14000,24000))])


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--freeze',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    root=a.freeze.resolve();manifest=load(root/'manifest.json')
    names=set();total=0
    for row in manifest['files']:
        path=(root/row['path']).resolve();assert path.is_relative_to(root)
        assert path.is_file() and path.stat().st_size==row['bytes'] and checksum(path)==row['sha256'],row['path']
        names.add(row['path']);total+=row['bytes']
    actual={path.relative_to(root).as_posix() for path in root.rglob('*') if path.is_file() and path!=root/'manifest.json'}
    assert actual==names
    base=Path(manifest['base_freeze']);assert checksum(base/'manifest.json')==manifest['base_manifest_sha256']
    milestone=load(root/'repo/research/startup_handoff_v1_verification.json')
    repo=Path(__file__).resolve().parents[1]
    for name,value in milestone['source_files'].items():assert checksum(root/'repo'/name)==checksum(repo/name)==value,name
    assert checksum(root/'binaries/vsl_source_bridge_v10.dll')==milestone['bridge_sha256']
    assert checksum(root/'binaries/vsl_source_bridge_v9.dll')==milestone['old_bridge_sha256']
    assert milestone['runtime_C_H_changed']==['src/drive/drive.c'] and len(milestone['voices_unchanged'])==89
    assert len(milestone['verification']['exact_cases'])==26 and len(milestone['verification']['neutral_cases'])==12
    work=root/'evidence';observed=load(work/'observation2/report.json')
    reference=observed['original_reference'];source=Path(reference['path'])
    assert checksum(source)==reference['sha256']
    with sf.SoundFile(source) as stream:
        stream.seek(reference['first_frame']);raw=stream.read(reference['last_frame']-reference['first_frame'],dtype='float64',always_2d=True)
    frozen,rate=sf.read(work/'observation2/A35-40.5-original.wav',dtype='float64',always_2d=True)
    assert rate==48000 and np.array_equal(raw,frozen)
    sources=[('reference',.25*raw,observed['original_reference_marker_bands'])]
    for row in observed['captures']:
        folder=work/row['variant']
        x,_=sf.read(folder/'mix.wav',dtype='float64',always_2d=True)
        sources.append((row['variant'],x,row['acoustic_marker_bands']))
        with (folder/'telemetry.csv').open(encoding='utf-8',newline='') as stream:telemetry=list(csv.DictReader(stream))
        blocked=[v for v in telemetry if int(v['lifecycle'])==4 and int(v['operating']) in (5,6)]
        assert len(blocked)*.005==row['startup_shift_block_seconds']
        if row['variant']!='original1':assert not blocked and all(int(v['shifts'])==0 and int(v['gear'])==0 for v in telemetry)
    cases=[]
    for label,x,regions in sources:
        for name,row in regions.items():
            y=x[row['first_frame']:row['last_frame']]
            expected=bands(y)
            np.testing.assert_allclose(expected,row['welch_band_power_LR'],rtol=2e-12,atol=1e-25)
            np.testing.assert_allclose(np.mean(y*y,axis=0),row['time_mean_power_LR'],rtol=2e-14,atol=1e-25)
            cases.append(dict(source=label,region=name,bands=6,channels=2))
    for name,value in load(work/'review2/report.json')['files'].items():assert checksum(work/'review2'/name)==value
    url='http://127.0.0.1:8789/references/analysis/startup_handoff_v1/review2/index.html'
    with urllib.request.urlopen(url,timeout=10) as response:served=response.read();assert response.status==200
    assert hashlib.sha256(served).hexdigest()==checksum(work/'review2/index.html')
    result=dict(schema='vsl.startup-handoff-independent-audit/1',result='passed',freeze=str(root),
        files=len(names),bytes=total,manifest_sha256=checksum(root/'manifest.json'),
        current_sources_and_binaries_exact=True,base_manifest_exact=True,
        raw_PCM_exact=True,independent_DFT_band_cases=cases,telemetry_interruption_verified=True,
        actual_review_HTTP_bytes_exact=True,review_url=url,timbre_accepted=False,goal_complete=False)
    assert not a.output.exists();a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(result='passed',files=len(names),bytes=total,independent_band_cases=len(cases))),flush=True)


if __name__=='__main__':main()

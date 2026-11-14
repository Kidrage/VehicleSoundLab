"""Replay one frozen case to check the default/legacy export seam unchanged."""
import argparse
import os
from pathlib import Path
import shutil
import struct
import sys
from research_archive_v1 import load,save,sha
p=argparse.ArgumentParser(description=__doc__)
for key in ('workspace','out'):p.add_argument('--'+key,type=Path,required=True)
p.add_argument('--recheck',type=Path)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
for key in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS'):os.environ[key]='2'
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
from local_voice_batch_v1.batch import fit_case
import numpy as np
import soundfile as sf
a.out.mkdir(parents=True,exist_ok=False)
r=dict(result='running',sources={})
try:
    for name in ['tools/verify_local_voice_legacy_v1.py','tools/local_voice_batch_v1/batch.py','tools/local_voice_batch_v1/render.py']:
        dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,dest);r['sources'][name]=sha(repo/name)
    parent=a.workspace/'baselines/F3_fifth_voice_v1';old=load(parent/'evidence/fit1/report.json')
    plan=load(repo/'research/F3_fifth_voice_v1_plan.json');case=plan['cases'][0]
    probe=a.workspace/'baselines/bandlimited_dna_v1/evidence/bin/frozen_old_raw_export.exe'
    assert sha(probe)==sha(parent/'inputs/raw_C_exporter')
    if a.recheck:
        previous=load(a.recheck/'report.json');assert previous['result']=='failed'
        assert previous['sources']['tools/local_voice_batch_v1/batch.py']==sha(repo/'tools/local_voice_batch_v1/batch.py')
        assert previous['sources']['tools/local_voice_batch_v1/render.py']==sha(repo/'tools/local_voice_batch_v1/render.py')
        replay_folder=a.recheck/case['name'];row=load(parent/'evidence/fit1'/case['name']/'result.json')
        r['rechecked_attempt']=str(a.recheck);r['rechecked_report_sha256']=sha(a.recheck/'report.json')
        r['no_new_extraction']=True
    else:
        replay_folder=a.out/case['name'];row=fit_case(a.workspace,case,plan,replay_folder,probe,repo)
    files=['native.wav','normalized.wav','coordinates.npz','voice.model','reference.wav']+['DNA_%d.wav'%s for s in plan['seeds']]
    r['exact']={n:sha(replay_folder/n)==sha(parent/'evidence/fit1'/case['name']/n) for n in files}
    # NPZ containers can vary zip timestamps; compare its actual coordinate
    # array if container bytes differ, without claiming archive-byte identity.
    if not r['exact']['coordinates.npz']:
        with np.load(replay_folder/'coordinates.npz') as x,np.load(parent/'evidence/fit1'/case['name']/'coordinates.npz') as y:
            assert np.array_equal(x['source_seconds'],y['source_seconds'])
    r['source_PCM_exact']={};r['WAV_container_differences']={}
    def without_peak_time(path):
        data=bytearray(path.read_bytes());at=12;stamps=[]
        assert data[:4]==b'RIFF' and data[8:12]==b'WAVE'
        while at+8<=len(data):
            tag,size=struct.unpack_from('<4sI',data,at)
            assert at+8+size<=len(data)
            if tag==b'PEAK':
                assert size==24 and struct.unpack_from('<I',data,at+8)[0]==1
                stamps.append(struct.unpack_from('<I',data,at+12)[0]);data[at+12:at+16]=b'\0'*4
            at+=8+size+(size&1)
        return data,stamps
    for name in ('native.wav','normalized.wav','reference.wav'):
        now=replay_folder/name;before=parent/'evidence/fit1'/case['name']/name
        x,xr=sf.read(now,always_2d=True);y,yr=sf.read(before,always_2d=True)
        assert xr==yr==48000 and np.array_equal(x,y)
        xx,xt=without_peak_time(now);yy,yt=without_peak_time(before)
        assert xx==yy
        r['source_PCM_exact'][name]=True
        r['WAV_container_differences'][name]=dict(only_PEAK_timestamp=True,new=xt,old=yt,whole_file_exact=r['exact'][name])
    assert all(r['exact'][name] for name in ['voice.model']+['DNA_%d.wav'%s for s in plan['seeds']])
    r.update(result='legacy_extraction_profile_and_three_C_WAVs_exact',coordinates_array_exact=True,
        root_hz=row['extraction']['root_hz'],raw_exporter_sha256=sha(probe),old_case=case)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(r['result'],flush=True)

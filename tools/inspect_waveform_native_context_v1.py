"""Trace the same six observations to recorded stereo and observed clock support.

Outer times are a coarse-clock availability estimate, NOT an extended corrected
phase map. Original coordinates and arrays remain untouched; no fit is run.
"""
import argparse
import os
import shutil
import sys
from pathlib import Path
from research_archive_v1 import load, save, sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('workspace','out'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args()
    for n in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[n]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    import soundfile as sf
    repo=Path(__file__).resolve().parents[1];a.out.mkdir(parents=True,exist_ok=False)
    shutil.copy2(__file__,a.out/'executed_inventory.py')
    r=dict(result='running',cases=[],inputs={},coordinate_unit='source_seconds',
        proposed_context_samples_each_side=2048,cycle_normalized_samples=1024,
        no_new_context_map_or_audio_or_fit=True)
    manifests={}
    def frozen(archive,relative):
        root=a.workspace/'baselines'/archive
        if archive not in manifests:
            digest=sha(root/'manifest.json')
            assert digest==load(repo/f'research/{archive}_summary.json')['manifest_sha256']
            manifests[archive]={v['path']:v['sha256'] for v in load(root/'manifest.json')['files']}
            r['inputs'][str(root/'manifest.json')]=digest
        path=root/relative;digest=sha(path);assert digest==manifests[archive][relative]
        r['inputs'][str(path)]=digest;return path
    try:
        geometry=load(frozen('coefficient_geometry_v1','evidence/real1/report.json'))
        source=load(frozen('observer_frequency_v1','evidence/real1/report.json'))
        prior={c['label']:c for c in source['cases']}
        for case in geometry['cases']:
            label=case['label'];relative=f"evidence/{case['attempt']}/{label}"
            selection=load(frozen(case['archive'],relative+'/selection.json'))
            result=load(frozen(case['archive'],relative+'/result.json'))
            native,rate=sf.read(frozen(case['archive'],relative+'/native.wav'),always_2d=True)
            assert rate==48000 and native.shape[1]==2
            with np.load(frozen(case['archive'],relative+'/coordinates.npz')) as z:
                coords=z['source_seconds']
            with np.load(frozen('observer_frequency_v1',f'evidence/real1/{label}/source.npz')) as z:
                audio=z['audio'];positions=z['positions']
                assert np.array_equal(native,z['native']) and np.array_equal(coords,z['coordinates'])
            with np.load(frozen('coefficient_geometry_v1',f'evidence/real1/{label}/source.npz')) as z:
                assert np.array_equal(audio,z['rebuilt']) and np.array_equal(native,z['native'])
                assert np.array_equal(coords,z['positions'])
            with np.load(frozen('observer_frequency_v1',f'evidence/real1/{label}/scale.npz')) as z:
                scale=z['scale'];assert scale.shape==(288,1) and np.all(scale>0)
            assert len(coords)==len(audio) and np.all(np.diff(coords)>0)
            start,stop=selection['case']['seconds']
            master=a.workspace/selection['provenance']['master']
            digest=sha(master);assert digest==selection['provenance']['master_sha256']
            r['inputs'][str(master)]=digest
            recorded,rate=sf.read(master,start=round(start*48000),stop=round(stop*48000),always_2d=True)
            assert rate==48000 and np.array_equal(recorded,native)
            assert len(native)==round((stop-start)*48000)
            family=selection['family'];assert family['status']=='connected_observed_family'
            times=np.array([v['seconds'] for v in family['rows']])
            hz=np.array([v['root_hz'] for v in family['rows']])
            assert np.all(np.diff(times)>0) and np.all(hz>0)
            phase=np.r_[0.,np.cumsum(np.diff(times)*(hz[:-1]+hz[1:])/2)]
            original_phase=np.interp(coords[[0,-1]],times,phase)
            desired_phase=original_phase+np.array([-2.,2.])
            coarse_supported=bool(phase[0]<=desired_phase[0]<desired_phase[1]<=phase[-1])
            coarse_seconds=np.interp(desired_phase,phase,times) if coarse_supported else None
            filter_guard_supported=bool(coarse_supported and coarse_seconds[0]-.1>=start and coarse_seconds[1]+.1<stop)
            corrected=result['extraction']['phase']['source_seconds']
            assert corrected==[float(coords[0]),float(coords[-1])]
            first=int(np.floor((coords[0]-start)*48000));last=int(np.ceil((coords[-1]-start)*48000))
            assert 4800<=first<last<len(native)-4800
            r['cases'].append(dict(label=label,archive=case['archive'],attempt=case['attempt'],
                frames=len(audio),nodes=len(positions),orders=288,channels=2,
                acoustic_root_hz=prior[label]['root_hz'],native_seconds=[start,stop],native_frames=len(native),
                original_source_seconds=corrected,original_coordinate_array_exact=True,
                original_audio_scale_and_native_exact=True,master_crop_bitwise_exact=True,
                real_samples_before=first,real_samples_after=len(native)-last-1,
                source_sample_step_range=(np.diff(coords)*48000)[[np.argmin(np.diff(coords)),np.argmax(np.diff(coords))]].tolist(),
                observed_coarse_clock_seconds=[float(times[0]),float(times[-1])],
                coarse_clock_two_cycle_each_side_supported=coarse_supported,
                coarse_context_seconds=None if coarse_seconds is None else coarse_seconds.tolist(),
                native_context_including_100ms_FIR_guard_supported=filter_guard_supported,
                original_heldout_coherence=result['extraction']['heldout_coherence'],
                outer_corrected_phase_independently_qualified=False,
                warning='Recorded neighbors and coarse clock availability do not qualify outer corrected phase, physical RPM or load'))
        assert len(r['cases'])==6
        r.update(result='waveform_native_context_provenance_inspected',
            all_master_crops_bitwise_exact=True,
            all_coarse_context_and_native_FIR_guards_available=all(c['native_context_including_100ms_FIR_guard_supported'] for c in r['cases']),
            extended_corrected_phase_or_real_fit_or_runtime_qualified=False)
        save(a.out/'report.json',r)
        print(r['result'],'recorded/coarse support',r['all_coarse_context_and_native_FIR_guards_available'],flush=True)
    except BaseException as error:
        r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise


if __name__=='__main__':main()

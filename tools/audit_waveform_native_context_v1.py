"""Independent scalar clock interpolation and original recording/crop audit."""
import argparse
import bisect
import math
import os
import shutil
import sys
from pathlib import Path
from research_archive_v1 import load, save, sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('workspace','study','out'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args()
    for n in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[n]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    import soundfile as sf
    a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_audit.py')
    repo=Path(__file__).resolve().parents[1]
    r=dict(result='running',cases=[],inputs={})
    manifest_cache={}
    def read(archive,name):
        root=a.workspace/'baselines'/archive
        if archive not in manifest_cache:
            digest=sha(root/'manifest.json')
            assert digest==load(repo/f'research/{archive}_summary.json')['manifest_sha256']
            manifest_cache[archive]={v['path']:v['sha256'] for v in load(root/'manifest.json')['files']}
            r['inputs'][str(root/'manifest.json')]=digest
        path=root/name;digest=sha(path);assert digest==manifest_cache[archive][name]
        r['inputs'][str(path)]=digest;return path
    def interpolate(x,xs,ys):
        assert xs[0]<=x<=xs[-1]
        j=min(max(bisect.bisect_right(xs,x)-1,0),len(xs)-2)
        return ys[j]+(ys[j+1]-ys[j])*(x-xs[j])/(xs[j+1]-xs[j])
    try:
        source=load(a.study/'report.json');r['inputs'][str(a.study/'report.json')]=sha(a.study/'report.json')
        assert source['result']=='waveform_native_context_provenance_inspected' and len(source['cases'])==6
        for name,digest in source['inputs'].items():assert sha(name)==digest
        parent=load(read('observer_frequency_v1','evidence/real1/report.json'))
        geometry=load(read('coefficient_geometry_v1','evidence/real1/report.json'))
        assert [c['label'] for c in source['cases']]==[c['label'] for c in geometry['cases']]
        frequencies={c['label']:c['root_hz'] for c in parent['cases']}
        for row in source['cases']:
            label=row['label'];archive=row['archive'];rel=f"evidence/{row['attempt']}/{label}"
            selection=load(read(archive,rel+'/selection.json'));result=load(read(archive,rel+'/result.json'))
            with np.load(read(archive,rel+'/coordinates.npz')) as z:coordinates=z['source_seconds']
            native,rate=sf.read(read(archive,rel+'/native.wav'),always_2d=True)
            start,stop=selection['case']['seconds'];assert row['native_seconds']==[start,stop]
            master=a.workspace/selection['provenance']['master']
            assert sha(master)==selection['provenance']['master_sha256'];r['inputs'][str(master)]=sha(master)
            crop,rate2=sf.read(master,start=round(start*48000),stop=round(stop*48000),always_2d=True)
            assert rate==rate2==48000 and np.array_equal(crop,native)
            with np.load(read('observer_frequency_v1',f'evidence/real1/{label}/source.npz')) as z:
                assert np.array_equal(native,z['native']) and np.array_equal(coordinates,z['coordinates'])
                assert len(z['audio'])==row['frames'] and len(z['positions'])==row['nodes']
                assert np.isfinite(z['audio']).all() and z['audio'].shape[1]==2
                with np.load(read('coefficient_geometry_v1',f'evidence/real1/{label}/source.npz')) as geometry_arrays:
                    assert np.array_equal(z['audio'],geometry_arrays['rebuilt'])
            with np.load(read('observer_frequency_v1',f'evidence/real1/{label}/scale.npz')) as z:
                assert z['scale'].shape==(288,1) and np.all(z['scale']>0)
            family=selection['family']['rows'];times=[v['seconds'] for v in family];hz=[v['root_hz'] for v in family]
            phase=[math.fsum((times[j+1]-times[j])*(hz[j+1]+hz[j])/2 for j in range(i)) for i in range(len(times))]
            first_phase=interpolate(float(coordinates[0]),times,phase)-2
            last_phase=interpolate(float(coordinates[-1]),times,phase)+2
            assert phase[0]<=first_phase<last_phase<=phase[-1]
            lo,hi=interpolate(first_phase,phase,times),interpolate(last_phase,phase,times)
            assert max(abs(lo-row['coarse_context_seconds'][0]),abs(hi-row['coarse_context_seconds'][1]))<1e-12
            assert lo-.1>=start and hi+.1<stop
            before=math.floor((float(coordinates[0])-start)*48000)
            after=len(native)-math.ceil((float(coordinates[-1])-start)*48000)-1
            assert before==row['real_samples_before'] and after==row['real_samples_after']
            assert row['original_source_seconds']==[float(coordinates[0]),float(coordinates[-1])]
            assert row['acoustic_root_hz']==frequencies[label]
            assert row['original_heldout_coherence']==result['extraction']['heldout_coherence']
            assert not row['outer_corrected_phase_independently_qualified']
            r['cases'].append(dict(label=label,recorded_neighbors_and_coarse_FIR_support_verified=True,
                scalar_coarse_seconds=[lo,hi],outer_corrected_phase_NOT_qualified=True))
        assert source['all_master_crops_bitwise_exact'] and source['all_coarse_context_and_native_FIR_guards_available']
        assert not source['extended_corrected_phase_or_real_fit_or_runtime_qualified']
        r.update(result='independent_waveform_native_context_provenance_verified',pass_count=6,
            producer_sha256=sha(a.study/'report.json'),auditor_sha256=sha(__file__),
            extended_phase_or_new_audio_or_fit_or_runtime_qualified=False)
        save(a.out/'report.json',r);print(r['result'],6,flush=True)
    except BaseException as error:
        r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise


if __name__=='__main__':main()

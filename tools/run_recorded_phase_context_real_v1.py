"""Genuine context for the same frozen F3 observations, no source inverse fit."""
import argparse
import os
import shutil
import sys
from pathlib import Path
from research_archive_v1 import load,save,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('workspace','known','known-audit','out'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args()
    for n in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[n]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    import soundfile as sf
    from recorded_phase_context_v1.mapping import extend
    from recorded_phase_context_v1.metrics import heldout
    repo=Path(__file__).resolve().parents[1];a.out.mkdir(parents=True,exist_ok=False)
    r=dict(result='running',cases=[],sources={},inputs={},no_source_inverse_or_runtime=True)
    names=['tools/run_recorded_phase_context_real_v1.py','tools/exterior_clock_v1/warp.py',
           'research/recorded_phase_context_v1_plan.json','research/recorded_phase_context_real_v1_plan.json',
           'research/F3_pitch_anchors_v1_plan.json']
    names.extend(p.relative_to(repo).as_posix() for p in (repo/'tools/recorded_phase_context_v1').glob('*.py'))
    manifests={}
    def binding(path):
        path=Path(path);r['inputs'][str(path)]=sha(path);return path
    def frozen(archive,relative):
        root=a.workspace/'baselines'/archive
        if archive not in manifests:
            path=binding(root/'manifest.json')
            assert sha(path)==load(repo/f'research/{archive}_summary.json')['manifest_sha256']
            manifests[archive]={x['path']:x['sha256'] for x in load(path)['files']}
        path=binding(root/relative);assert sha(path)==manifests[archive][relative];return path
    try:
        known=load(binding(a.known/'report.json'));audit=load(binding(a.known_audit/'report.json'))
        assert known['all_qualified'] and audit['all_qualified'] and audit['pass_count']==8
        assert audit['result']=='independent_recorded_phase_context_known_verified'
        assert audit['producer_sha256']==sha(a.known/'report.json')
        for name in names:
            path=a.out/'exact_sources'/name;path.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(repo/name,path);r['sources'][name]=sha(path)
        original_plan=load(repo/'research/F3_pitch_anchors_v1_plan.json')
        gate=original_plan['gates']['heldout_carrier_coherence'];assert gate==.8
        geometry=load(frozen('coefficient_geometry_v1','evidence/real1/report.json'))
        for case in geometry['cases']:
            label=case['label'];relative=f"evidence/{case['attempt']}/{label}"
            selection_path=frozen(case['archive'],relative+'/selection.json');selection=load(selection_path)
            result_path=frozen(case['archive'],relative+'/result.json');result=load(result_path)
            coords_path=frozen(case['archive'],relative+'/coordinates.npz')
            native_path=frozen(case['archive'],relative+'/native.wav')
            native,rate=sf.read(native_path,always_2d=True);assert rate==48000
            lo,hi=selection['case']['seconds']
            master=binding(a.workspace/selection['provenance']['master'])
            assert sha(master)==selection['provenance']['master_sha256']
            raw,rate=sf.read(master,start=round(lo*48000),stop=round(hi*48000),always_2d=True)
            assert rate==48000 and np.array_equal(raw,native)
            source_path=frozen('observer_frequency_v1',f'evidence/real1/{label}/source.npz')
            scale_path=frozen('observer_frequency_v1',f'evidence/real1/{label}/scale.npz')
            with np.load(source_path) as z:
                old=z['audio'];where=z['coordinates'];assert np.array_equal(native,z['native'])
            with np.load(coords_path) as z:assert np.array_equal(where,z['source_seconds'])
            with np.load(scale_path) as z:scale=z['scale']
            family=selection['family'];assert family['status']=='connected_observed_family'
            times=np.array([x['seconds'] for x in family['rows']]);hz=np.array([x['root_hz'] for x in family['rows']])
            aperture=result['extraction']['aperture_source_seconds'];cutoff=result['extraction']['phase']['source_cutoff_hz']
            arrays,info=extend(native,lo,times,hz,aperture,old,where,cutoff)
            carrier=heldout(arrays)
            minimum=min(min(v['coherence']) for x in carrier.values() for v in x.values())
            file=a.out/(label+'.npz')
            np.savez_compressed(file,native=native,source_start=lo,clock_times=times,root_hz=hz,
                aperture=aperture,original_scale=scale,**arrays)
            r['cases'].append(dict(label=label,file=file.name,sha256=sha(file),info=info,
                original_bindings=dict(selection=str(selection_path),result=str(result_path),coordinates=str(coords_path),
                    observer_source=str(source_path),scale=str(scale_path),native=str(native_path)),
                heldout=carrier,original_heldout=result['extraction']['heldout_coherence'],
                minimum_coherence=minimum,qualified=bool(minimum>=gate)))
            save(a.out/'report.json',r)
            print(label,'phase',minimum>=gate,'minimum coherence',minimum,flush=True)
        assert len(r['cases'])==6
        r.update(result='recorded_phase_context_real_measured',
            all_qualified=all(c['qualified'] for c in r['cases']),original_heldout_gate=gate,
            acoustic_coordinate_only=True,no_physical_RPM_or_load_or_runtime_or_hearing_qualification=True)
        save(a.out/'report.json',r)
    except BaseException as e:
        r.update(result='failed',error=repr(e));save(a.out/'report.json',r);raise


if __name__=='__main__':main()

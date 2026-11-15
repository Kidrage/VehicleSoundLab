"""Prepare exact actual native48k intervals and source-FIR-only references."""
import argparse
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load,save,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('workspace','preparation','preparation-audit','known','known-audit','out'):
        p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from scipy import signal
    from native_clock_render_v1.geometry import dense_query
    from extraction_sound_v1.measure import measure
    from extraction_sound_v1.compare import compare
    from extraction_sound_v1.consume import qualification,precision
    repo=Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True,exist_ok=False)
    r=dict(result='running',cases=[],sources={},inputs={})
    def read(path):
        path=Path(path);r['inputs'][str(path)]=sha(path);return load(path)
    try:
        prepared=read(a.preparation/'report.json');pa=read(a.preparation_audit/'report.json')
        known=read(a.known/'report.json');ka=read(a.known_audit/'report.json')
        assert prepared['result']=='waveform_file_real_six_prepared' and len(prepared['cases'])==6
        assert pa['all_qualified'] and pa['producer_sha256']==sha(a.preparation/'report.json')
        for name,digest in prepared['inputs'].items():
            assert sha(name)==digest;r['inputs'][name]=digest
        assert ka['all_known_qualified'] and len(ka['cases'])==13 and ka['producer_sha256']==sha(a.known/'report.json')
        for name,digest in known['sources'].items():
            if name.startswith('tools/native_clock_render_v1/'):
                assert sha(repo/name)==sha(a.known/'exact_sources'/name)==digest
        meter_root=a.workspace/'references/analysis/extraction_sound_v1'
        r['meter_protocol']=qualification(repo,meter_root/'known2',meter_root/'known_composed_audit1')
        for folder in ('known2','known_composed_audit1'):read(meter_root/folder/'report.json')
        live_path=a.workspace/'references/analysis/waveform_file_real_v1/real1/run_spec.json'
        live=read(live_path)
        assert all(sha(repo/name)==digest for name,digest in live['sources'].items())
        names={'tools/prepare_native_clock_real_v1.py','tools/audit_native_clock_preparation_v1.py',
            'research/native_clock_render_v1_plan.json','research/native_clock_preparation_v1_plan.json',
            'tools/research_archive_v1.py'}
        names.update(p.relative_to(repo).as_posix() for directory in ('native_clock_render_v1','extraction_sound_v1')
            for p in (repo/'tools'/directory).glob('*.py'))
        for name in sorted(names):
            path=a.out/'exact_sources'/name;path.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(repo/name,path);r['sources'][name]=sha(path)
        for c in prepared['cases']:
            path=a.preparation/c['file'];assert sha(path)==c['sha256'];r['inputs'][str(path)]=sha(path)
            with np.load(path) as f:z={k:f[k] for k in f.files}
            context_path=Path(c['context_file']);r['inputs'][str(context_path)]=sha(context_path)
            archive=context_path.parents[2]
            manifest=read(archive/'manifest.json')
            entries={v['path']:v['sha256'] for v in manifest['files']}
            assert entries[(context_path.parent/'report.json').relative_to(archive).as_posix()]==sha(context_path.parent/'report.json')
            context=read(context_path.parent/'report.json')
            row=next(v for v in context['cases'] if v['label']==c['label'])
            assert row['sha256']==sha(context_path) and row['qualified']
            with np.load(context_path) as original:
                assert np.array_equal(original['positions'],z['source_coordinates'])
                assert np.array_equal(original['native'],z['native'])
            assert np.array_equal(z['source_coordinates'][2048:-2048],z['target_source_coordinates'])
            assert np.array_equal(z['orders'],np.arange(1,289))
            start=float(z['source_start']);coords=z['target_source_coordinates']
            first=int(np.ceil((coords[0]-start)*48000));stop=int(np.floor((coords[-1]-start)*48000))+1
            count=stop-first;native_start=start+first/48000
            assert count>=4096 and first>=512 and stop<=len(z['native'])-512
            cutoff=float(row['info']['cutoff_hz'])
            taps=signal.firwin(1025,cutoff,fs=48000,window=('kaiser',12))
            full=signal.fftconvolve(z['native'],taps[:,None],mode='valid',axes=0)
            raw=z['native'][first:stop].copy();filtered=full[first-512:stop-512]
            arrays=dict(raw_native_target=raw,source_FIR_only_target=filtered,source_FIR_taps=taps,
                source_coordinates=z['source_coordinates'],target_source_coordinates=coords,
                original_positions=z['original_positions'],positions=z['positions'],orders=z['orders'],
                native_start=np.array(native_start),registered_start=z['source_start'],first=np.array(first),stop=np.array(stop))
            geometry={}
            for up in (16,32):
                query,times,info=dense_query(z['source_coordinates'],native_start,count,up=up,delay=128*up)
                arrays['query'+str(up)]=query;geometry[str(up)]=info
            raw_measured,filtered_measured=measure(raw,48000),measure(filtered,48000)
            arrays.update({'raw_'+key:value for key,value in raw_measured.items()})
            arrays.update({'FIR_only_'+key:value for key,value in filtered_measured.items()})
            output=a.out/(c['label']+'.npz');np.savez_compressed(output,**arrays)
            r['cases'].append(dict(label=c['label'],file=output.name,sha256=sha(output),
                original_preparation=str(path),original_preparation_sha256=sha(path),context_report=str(context_path.parent/'report.json'),
                source_cutoff_hz=cutoff,native_frames=count,native_first=first,native_stop=stop,
                native_start_seconds=native_start,geometry=geometry,
                source_FIR_only_signed_changes=compare(filtered_measured,raw_measured),
                raw_precision=precision(raw_measured),FIR_only_precision=precision(filtered_measured),
                prior_interpolator_not_undone_or_included=True,actual_fitted_render_available=False))
            save(a.out/'report.json',r);print('NATIVE_PREPARED',c['label'],count,'source cutoff',cutoff,flush=True)
        assert all(sha(repo/name)==digest for name,digest in live['sources'].items())
        r.update(result='native_clock_six_real_intervals_prepared',all_registered_intervals_and_guards_passed=True,
            no_fitted_render_or_sustained_source_or_C_or_hearing_qualification=True)
        save(a.out/'report.json',r)
    except BaseException as error:
        r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise


if __name__=='__main__':main()

"""Bind ALL six original/context objectives before ONE separately launched fit."""
import argparse
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load,save,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('workspace','known','known-audit','out'):p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args()
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from waveform_file_real_v1.prepare import build
    from waveform_file_real_v1.resources import preflight
    repo=Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True,exist_ok=False)
    r=dict(result='running',cases=[],inputs={},sources={},no_inverse_fit=True)
    try:
        def bind(path):
            path=Path(path);r['inputs'][str(path)]=sha(path);return path
        known,audit=load(bind(a.known/'report.json')),load(bind(a.known_audit/'report.json'))
        assert known['all_qualified'] and audit['all_qualified'] and len(audit['cases'])==4
        assert audit['producer_sha256']==sha(a.known/'report.json')
        for name,digest in known['sources'].items():assert sha(repo/name)==sha(a.known/'exact_sources'/name)==digest
        full=a.workspace/'baselines/waveform_file_full_v1'
        summary=load(bind(repo/'research/waveform_file_full_v1_summary.json'))
        assert sha(bind(full/'manifest.json'))==summary['manifest_sha256']
        fm={x['path']:x['sha256'] for x in load(full/'manifest.json')['files']}
        for key in ('independent_archive_verification','independent_binding_verification'):
            receipt=summary[key];assert sha(bind(receipt['path']))==receipt['sha256']
        for folder in ('full_audit1','peak_audit1','resources_audit1'):
            path=bind(full/'evidence'/folder/'report.json')
            assert sha(path)==fm[f'evidence/{folder}/report.json'] and load(path)['all_qualified']
        for file,count in (('C_files_sha256.json',670),('voice_files_sha256.json',82),('F2_files_sha256.json',3)):
            path=bind(full/'evidence'/file);assert sha(path)==fm['evidence/'+file]
            values=load(path);assert len(values)==count and all(sha(repo/n)==h for n,h in values.items())
        assert sha(repo/'handoff/C文件索引.csv')==sha(full/'source/handoff/C文件索引.csv')
        assert all(sha(repo/n)==h for n,h in summary['protected_hearings_sha256'].items())
        archive=a.workspace/'baselines/recorded_phase_context_v1'
        cs=load(bind(repo/'research/recorded_phase_context_v1_summary.json'))
        assert sha(bind(archive/'manifest.json'))==cs['manifest_sha256']
        manifest={x['path']:x['sha256'] for x in load(archive/'manifest.json')['files']}
        def frozen(relative):
            path=bind(archive/relative);assert sha(path)==manifest[relative];return path
        data=load(frozen('evidence/real1/report.json'))
        phase=load(frozen('evidence/real_audit1/report.json'))
        assert phase['all_qualified'] and phase['pass_count']==6 and phase['producer_sha256']==sha(archive/'evidence/real1/report.json')
        mapping=load(frozen('validation.json'))['original_input_archive_locations']
        frequency=a.workspace/'baselines/observer_frequency_v1'
        fs=load(bind(repo/'research/observer_frequency_v1_summary.json'))
        assert sha(bind(frequency/'manifest.json'))==fs['manifest_sha256']
        fmanifest={x['path']:x['sha256'] for x in load(frequency/'manifest.json')['files']}
        order_source=bind(frequency/'source/tools/run_observer_frequency_real_v1.py')
        assert sha(order_source)==fmanifest['source/tools/run_observer_frequency_real_v1.py']
        assert 'WaveSynthesis(len(audio), positions, np.arange(1, 289))' in order_source.read_text(encoding='utf-8')
        names=set(known['sources'])|{'tools/prepare_waveform_file_real_v1.py','tools/audit_waveform_file_real_preparation_v1.py','research/waveform_file_real_v1_plan.json'}
        for name in sorted(names):
            dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(repo/name,dest);r['sources'][name]=sha(dest)
        for case in data['cases']:
            context_path=frozen('evidence/real1/'+case['file'])
            assert sha(context_path)==case['sha256']
            with np.load(context_path) as z:raw={name:z[name] for name in z.files}
            original_paths={key:frozen(mapping[path]) for key,path in case['original_bindings'].items()}
            with np.load(original_paths['observer_source']) as old:
                positions=old['positions'];assert np.array_equal(old['audio'],raw['original_audio'])
                assert np.array_equal(old['coordinates'],raw['original_positions']) and np.array_equal(old['native'],raw['native'])
            with np.load(original_paths['scale']) as old:assert np.array_equal(old['scale'],raw['original_scale'])
            orders=np.arange(1,289)
            system,shared,reference=build(raw['audio'],raw['original_audio'],positions,orders,raw['original_scale'])
            t=np.arange(system.nsize)
            q=.01*np.sin(.173*t)+.007*np.cos(.071*t)
            from observer_inverse_v1.fit import complex_array
            wave=system.synthesis.synthesize(complex_array(q,system.nshape)*system.scale[None])
            metric=system.metric
            output=dict(audio=raw['audio'],target=raw['original_audio'],original_positions=positions,
                positions=system.synthesis.positions,orders=orders,scale=raw['original_scale'],native=raw['native'],
                source_coordinates=raw['positions'],target_source_coordinates=raw['original_positions'],
                clock_times=raw['clock_times'],root_hz=raw['root_hz'],source_start=raw['source_start'],aperture=raw['aperture'],
                weights=metric.weights,band_power=metric.band_power,floor_active=metric.floor_active,
                sigma=np.array(metric.wave_scale),amplitude=np.array(metric.amplitude_scale),
                target_slots=metric.target_window_slots,probe_q=q,probe_wave=wave,probe_spectrum=metric.forward(wave))
            path=a.out/(case['label']+'.npz');np.savez_compressed(path,**output)
            resource=preflight(a.out,len(raw['audio']),len(output['positions']),288,1024)
            r['cases'].append(dict(label=case['label'],file=path.name,sha256=sha(path),
                context_file=str(context_path),original_files={k:str(v) for k,v in original_paths.items()},
                order_source=str(order_source),orders_provenance='Explicit original executed WaveSynthesis(...,np.arange(1,289))',
                frames=len(raw['audio']),target_frames=len(raw['original_audio']),nodes=len(output['positions']),orders=288,
                resources=resource,metric_origin='original joint LR target only; outer data add positive constraints'))
            save(a.out/'report.json',r)
            print('REAL_PREP',case['label'],len(raw['audio']),len(output['positions']),resource['memory_passed'],flush=True)
        assert len(r['cases'])==6
        disk=sum(c['resources']['full_factor_disk_bytes'] for c in r['cases'])
        r.update(result='waveform_file_real_six_prepared',all_resources_passed=all(c['resources']['memory_passed'] and c['resources']['disk_passed'] for c in r['cases']),
            retained_six_factor_bytes=disk,required_six_disk_bytes=disk+2*1024**3,
            retained_six_disk_passed=min(c['resources']['available_disk_bytes'] for c in r['cases'])>=disk+2*1024**3,
            one_V10_two_rises=True,no_source_or_C_or_hearing_qualification=True)
        save(a.out/'report.json',r)
    except BaseException as error:
        r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise


if __name__=='__main__':main()

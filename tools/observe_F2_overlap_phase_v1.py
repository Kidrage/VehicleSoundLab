"""Compare original and once-corrected local trajectories in all six F2 overlap pairs."""
import argparse
import json
from pathlib import Path
import shutil
import sys

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
args=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
from drive_evidence_v1.sources import read,sha
from line_motion_v1.overlap_phase import adjacent_overlaps,line_from_fit,compare
from line_motion_v1.local_precision_controls import controls
from line_motion_v1.local_precision import fit_channel


args.out.mkdir(parents=True,exist_ok=False)
report=dict(schema='vsl.F2-overlap-phase/2',result='running',sources={},real_audio_read=False,
    model_exported=False,runtime_changed=False,real_nonlinear_fits=0,phase_alignment_applied=False)
try:
    for path in (Path(__file__),repo/'research/F2_overlap_phase_v1_plan.json',repo/'research/F2_local_precision_v1_plan.json',repo/'references/segments_v1.json',
        repo/'tools/drive_evidence_v1/sources.py',*sorted((repo/'tools/line_motion_v1').glob('*.py'))):
        relative=path.relative_to(repo);target=args.out/'exact_sources'/relative
        target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target);report['sources'][relative.as_posix()]=sha(path)
    report['controls']=controls();assert report['controls']['passed'],'Known continuity control failed; no recording read'
    root=args.workspace/'references/analysis/F2_rate_coordinates_v1';parent_path=root/'observe1/report.json'
    parent=json.loads(parent_path.read_text(encoding='utf-8'))
    parent_arrays=np.load(root/'observe1/observations.npz')
    assert sha(root/'observe1/observations.npz')==parent['arrays_sha256']
    audio,provenance=read(args.workspace,'F2_tailpipe','fixed_window_spectral_observation');report['real_audio_read']=True
    assert provenance==parent['provenance'] and np.array_equal(audio,parent_arrays['audio'])
    local=[]
    for row in parent['observations']:
        start=round((row['source_seconds'][0]-6)*48000);part=audio[start:start+48000];channels=[]
        for ch,item in enumerate(row['channels']):
            nominal=np.array(item['new_fit']['nominal_Hz'])
            parameters,fit=fit_channel(part[:,ch],48000,nominal)
            assert fit['original_fit']==item['new_fit']
            channels.append(dict(channel=ch,new_fit=fit))
        local.append(dict(source_seconds=row['source_seconds'],channels=channels))
    report['real_nonlinear_fits']=18
    pairs,gaps=adjacent_overlaps(parent['observations'],48000)
    assert [(r['left_window'],r['right_window']) for r in pairs]==[(0,1),(1,2),(3,4),(4,5),(6,7),(7,8)]
    rows=[];saved={key:[] for key in ('old_left','old_right','new_left','new_right')}
    for pair in pairs:
        left=parent['observations'][pair['left_window']];right=parent['observations'][pair['right_window']]
        samples=np.arange(pair['first_sample'],pair['stop_sample']);channels=[];pair_waves={k:[] for k in saved}
        for ch in range(2):
            comparisons=[];channel_waves={k:[] for k in saved}
            for j in range(3):
                a=line_from_fit(left['channels'][ch]['new_fit'],left['source_seconds'],j)
                b=line_from_fit(right['channels'][ch]['new_fit'],right['source_seconds'],j)
                old,v1,v2=compare(a,b,samples,48000)
                na=line_from_fit(local[pair['left_window']]['channels'][ch]['new_fit'],left['source_seconds'],j)
                nb=line_from_fit(local[pair['right_window']]['channels'][ch]['new_fit'],right['source_seconds'],j)
                new,n1,n2=compare(na,nb,samples,48000)
                comparisons.append(dict(main_slot=j,correspondence='same_designated_main_slot_NOT_physical_identity',old=old,new=new))
                for k,v in zip(saved,(v1,v2,n1,n2)):channel_waves[k].append(v)
            channels.append(dict(channel=ch,comparisons=comparisons))
            for k in saved:pair_waves[k].append(np.column_stack(channel_waves[k]))
        rows.append(dict(**pair,source_overlap_seconds=[pair['first_sample']/48000,pair['stop_sample']/48000],channels=channels))
        for k in saved:saved[k].append(np.stack(pair_waves[k],axis=1))
    np.savez_compressed(args.out/'overlaps.npz',**{k:np.stack(v) for k,v in saved.items()})
    report.update(result='all18_once_corrected_fits_and72_overlap_comparisons_NOT_shared_clock_qualification',
        provenance=provenance,parent_report_sha256=sha(parent_path),parent_arrays_sha256=parent['arrays_sha256'],
        local_fits=local,observations=rows,unconnected_adjacent_pairs=gaps,arrays_sha256=sha(args.out/'overlaps.npz'),
        original_failed_observation_report_sha256=sha(args.workspace/'references/analysis/F2_overlap_phase_v1/observe1/report.json'),
        counts=dict(overlap_pairs=6,channels=2,main_slots=3,parent_comparisons=36,corrected_comparisons=36,samples_per_comparison=24000),
        phase_extracted_real_model_permitted=False,shared_phase_clock_fit=False,RPM_inferred=False,
        limits=['Shared overlap samples are not independent heldout validation',
            'Same designated main slots are not proven physical source identities',
            'Agreement is local-model consistency only; disagreement can arise from nonquadratic phase, interference or fit errors',
            'No phase rotation, offset removal, forced gap or model synthesis was applied'])
    print(json.dumps(dict(result=report['result'],counts=report['counts'],rows=[dict(pair=[r['left_window'],r['right_window']],
        old_phase_rms_cycles=[x['old']['wrapped_phase_rms_cycles'] for x in r['channels'][0]['comparisons']],
        new_phase_rms_cycles=[x['new']['wrapped_phase_rms_cycles'] for x in r['channels'][0]['comparisons']],
        frequency_max_Hz=[x['new']['frequency_difference_max_Hz'] for x in r['channels'][0]['comparisons']]) for r in rows])),flush=True)
except Exception as exc:report.update(result='failed',error=repr(exc));raise
finally:(args.out/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')

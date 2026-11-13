"""Independently audit all generated signals, fits, observations and exact paths."""
import argparse
import math
import shutil
import sys
from pathlib import Path

p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','input','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args()
repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
from research_archive_v1 import load,save,sha
from native_chirp_audit_v1.wave import near,audit_wave
from native_chirp_audit_v1.temporal import audit_temporal
from chirp_motion_controls_v1.audit_inputs import signal,truth_rows,inventory,initialization

a.out.mkdir(parents=True,exist_ok=False)
r=dict(result='running',windows=0,lines=0,maximum_signal_error=0.,maximum_waveform_error=0.,
    maximum_inventory_error=0.,maximum_support_error=0.,maximum_phase_arithmetic_error=0.,summaries=[],true_components=[])
for name in ['tools/audit_chirp_motion_controls_v1.py','tools/chirp_motion_controls_v1/audit_inputs.py',
    'tools/native_chirp_audit_v1/wave.py','tools/native_chirp_audit_v1/temporal.py']:
    dest=a.out/'exact_sources'/name
    dest.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(repo/name,dest)
try:
    report=load(a.input/'report.json')
    assert report['result']=='all60_native_AM_FM_mono_noise_mechanism_controls_complete' and report['real_source_read'] is False
    for name,h in report['sources'].items():
        assert sha(a.input/'exact_sources'/name)==h==sha(repo/name)
    plan=report['plan']
    fp=load(repo/'research/accel_chirp_v1_plan.json')
    rp=load(repo/'research/accel_ridges_v1_plan.json')
    lp=load(repo/'research/low_chirp_v1_plan.json')
    for case in plan['cases']:
        folder=a.input/case
        native=np.load(folder/'signal.npz')['audio']
        expected=signal(case,plan)
        r['maximum_signal_error']=max(r['maximum_signal_error'],near(native,expected,2e-12))
        rows=load(folder/'fits.json')
        assert len(rows)==12
        obs=load(folder/'initialization.json')
        truth=load(folder/'truth.json')
        truth_rows(case,plan,truth['rows'])
        for i,row in enumerate(rows):
            z=np.load(folder/f'tile_{i:02d}.npz')
            near(z['audio'],native[i*12000:(i+1)*12000],0)
            inv=inventory(z['audio'],obs['inventories'][i],rp)
            r['maximum_inventory_error']=max(r['maximum_inventory_error'],inv['error'])
            assert inv['strongest_index']==obs['guides'][i]['native_inventory_index']
            near(inv['strongest_hz'],obs['guides'][i]['observed_hz'],1e-8)
            near(obs['ratios'][i],obs['guides'][i]['observed_hz']/obs['guides'][0]['observed_hz'])
            out=audit_wave(z,row,fp)
            r['windows']+=1
            r['lines']+=out['lines']
            r['maximum_waveform_error']=max(r['maximum_waveform_error'],out['waveform_error'])
            r['maximum_support_error']=max(r['maximum_support_error'],out['support_error'])
            if row['lines']:
                m=len(row['lines'])
                near(z['nominal'],np.array(obs['inventories'][i]['bin'])*4)
                near(z['initial'][m:2*m],np.clip(obs['initial'][i]['initial_chirp'],-500+1e-6,500-1e-6))
        initialization(obs['inventories'],obs['ratios'],obs['initial'])
        linked=load(folder/'temporal.json')
        value=audit_temporal(rows,linked,lp)
        r['maximum_phase_arithmetic_error']=max(r['maximum_phase_arithmetic_error'],value['maximum_phase_arithmetic_error'])
        if truth['rows']:
            value=audit_temporal(truth['rows'],truth['temporal'],lp)
            r['maximum_phase_arithmetic_error']=max(r['maximum_phase_arithmetic_error'],value['maximum_phase_arithmetic_error'])
        else:
            assert truth['temporal'] is None and truth['pairs']==[] and truth['inequalities']==[]
        expected_pairs=[]
        for i,(row,actual) in enumerate(zip(rows,truth['rows'])):
            picks=[min(range(len(row['lines'])),key=lambda j:abs(row['lines'][j]['frequency_hz']-e['frequency_hz'])) for e in actual['lines']]
            for e,k in zip(actual['lines'],picks):
                v=row['lines'][k]
                expected_pairs.append(dict(window=i,component=e['index'],fitted_line=k,nearest_is_unique=picks.count(k)==1,
                    eligible=v['eligible'],optimizer_success=row['success'],frequency_error_hz=v['frequency_hz']-e['frequency_hz'],
                    chirp_error_hz_per_second=v['chirp_hz_per_second']-e['chirp_hz_per_second'],
                    amplitude_error_db_LR=[20*math.log10(max(x,1e-300)/y) for x,y in zip(v['amplitude_LR'],e['amplitude_LR'])]))
        assert len(expected_pairs)==len(truth['pairs'])
        for expected,stored in zip(expected_pairs,truth['pairs']):
            assert expected.keys()==stored.keys()
            for key,value in expected.items():
                if key in ['frequency_error_hz','chirp_error_hz_per_second','amplitude_error_db_LR']:near(value,stored[key])
                else:assert value==stored[key]
        inequalities=[]
        for i in range(1,len(truth['rows'])):
            for e,f in zip(truth['rows'][i-1]['lines'],truth['rows'][i]['lines']):
                forward=f['frequency_hz']-e['frequency_hz']-.25*e['chirp_hz_per_second']
                backward=e['frequency_hz']-f['frequency_hz']+.25*f['chirp_hz_per_second']
                dq=f['chirp_hz_per_second']-e['chirp_hz_per_second']
                inequalities.append(dict(previous_window=i-1,current_window=i,component=e['index'],
                    forward_error_hz=forward,backward_error_hz=backward,chirp_difference=dq,
                    fails_frequency_prediction=max(abs(forward),abs(backward))>.5,
                    fails_chirp_difference=abs(dq)>8,same_component_passes=max(abs(forward),abs(backward))<=.5 and abs(dq)<=8))
        assert inequalities==truth['inequalities']
        def tracks(obj,low):
            selected=[] if obj is None else [v for v in obj['tracks'] if not low or v['frequencies_hz'][0]<200]
            return dict(count=len(selected),longest=max([len(v['windows']) for v in selected],default=0),atleast5=sum(len(v['windows'])>=5 for v in selected))
        unique=[v for v in expected_pairs if v['nearest_is_unique']]
        low=[v for v in inequalities if v['component']<6]
        item=dict(case=case,windows=len(rows),successful=sum(v['success'] for v in rows),inventories=[len(v['lines']) for v in rows],
            capacity_or_empty=[i for i,v in enumerate(rows) if v['reason']=='empty_or_overflow'],eligible_lines=sum(v['eligible'] for row in rows for v in row['lines']),
            fitted_low_tracks=tracks(linked,True),exact_low_tracks=tracks(truth['temporal'],True),fitted_all_tracks=tracks(linked,False),exact_all_tracks=tracks(truth['temporal'],False),
            maximum_unique_frequency_error_hz=max([abs(v['frequency_error_hz']) for v in unique],default=None),
            maximum_unique_chirp_error_hzs=max([abs(v['chirp_error_hz_per_second']) for v in unique],default=None),
            exact_low_same_component_edges=len(low),exact_low_frequency_failures=sum(v['fails_frequency_prediction'] for v in low),
            exact_low_rate_difference_failures=sum(v['fails_chirp_difference'] for v in low))
        assert item==next(v for v in report['summaries'] if v['case']==case)
        r['summaries'].append(item)
        if truth['rows']:
            components=[]
            for k in range(10):
                identities={node['track_id'] for frame in truth['temporal']['frames'] for node in frame if node['index']==k}
                spans=[len(v['windows']) for v in truth['temporal']['tracks'] if v['track_id'] in identities]
                edges=[v for v in inequalities if v['component']==k]
                components.append(dict(component=k,base_hz=plan['base_hz'][k],moving=plan['moving'][k],
                    longest_exact_track=max(spans),exact_track_count=len(spans),passed_same_component_edges=sum(v['same_component_passes'] for v in edges)))
            r['true_components'].append(dict(case=case,components=components))
    for filename,count in [('C_files_sha256.json',612),('voice_files_sha256.json',67)]:
        table=load(a.workspace/'baselines/idle_microtexture_c_v1/inputs'/filename)
        assert len(table)==count
        for name,h in table.items():assert sha(repo/name)==h
    r.update(result='all60_known_native_signals_inventories_observed_initials_fits_truth_connections_verified',
        input_report_sha256=sha(a.input/'report.json'),C_H_unchanged=612,old_voices_unchanged=67,
        real_source_read=False,source_identity_or_RPM_or_common_phase_qualified=False)
except Exception as exc:
    r.update(result='failed',error=repr(exc))
    raise
finally:
    save(a.out/'report.json',r)
print({key:r[key] for key in ['result','windows','lines','maximum_signal_error','maximum_waveform_error','maximum_inventory_error']})

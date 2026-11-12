"""Attribute frozen clock losses to known components; inspect failed rapid passes."""
import argparse
import json
from pathlib import Path
import shutil
import sys

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True)
parser.add_argument('--out',type=Path,required=True)
args=parser.parse_args()
repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from drive_evidence_v1.sources import sha
from fractional_clock_v1.coordinate import warp
from fractional_clock_v1.phase import refine_once
from fractional_clock_v1.measure import moments,coherent_moments,compare
from exterior_clock_v1.warp import render_positions
from fractional_residue_v1.components import split,high_carriers
from fractional_residue_v1.observations import aperture,phase_residue,residue_summary,line_power


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')


def measure(audio,cycle,base,plan):
    return dict(total=moments(audio,cycle,base,plan['bands_hz'],plan['power_window_coarse_cycles']),
        grid=coherent_moments(audio,cycle,base,plan['bands_hz'],plan['coherent_power_window_coarse_cycles'],5))


args.out.mkdir(parents=True,exist_ok=False)
report=dict(schema='vsl.fractional-residue-diagnosis/1',result='running',sources={},cases=[],
    real_audio_read=False,qualification_changed=False,runtime_modified=False,profiles_exported=0)
try:
    task_path=repo/'research/fractional_residue_v1_plan.json'
    task=load(task_path)
    plan_path=repo/'research/fractional_clock_v1_plan.json'
    plan=load(plan_path)
    frozen=args.workspace/task['validation']
    validation=load(frozen/'report.json')
    assert validation['result']=='rejected'
    assert sha(plan_path)==validation['plan_sha256']
    for name,digest in validation['sources'].items():
        assert sha(repo/name)==sha(frozen/'exact_sources'/name)==digest
    sources=[task_path,Path(__file__)]+[repo/name for name in validation['sources']]
    sources+=list((repo/'tools/fractional_residue_v1').glob('*.py'))
    for source in sources:
        target=args.out/'exact_sources'/source.relative_to(repo)
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,target)
        report['sources'][source.relative_to(repo).as_posix()]=sha(source)
    report['validation_report_sha256']=sha(frozen/'report.json')
    cycle=plan['coordinate']['samples_per_coarse_cycle']
    figure,axes=plt.subplots(2,2,figsize=(13,8),layout='constrained')
    for case_id in task['cases']:
        item=next(row for row in validation['cases'] if row['case']['id']==case_id)
        case=item['case']
        directory=args.out/case_id
        directory.mkdir()
        full,parts,t,phase,frequency,reconstruction=split(case,plan['seconds'])
        assert reconstruction<=task['linearity_tolerance_fs']
        output=dict(case=case,component_reconstruction_error_fs=reconstruction,frozen_status=item['status'])
        if item['status']=='measured':
            saved=frozen/case_id/'coordinates.npz'
            output['frozen_coordinates_sha256']=sha(saved)
            with np.load(saved,allow_pickle=False) as archive:
                positions=archive['source_seconds']
            origin=np.interp(positions[0],t,phase)
            oracle_positions=np.interp(origin+np.arange(len(positions))/cycle,phase,t)
            cutoff=item['phase']['source_cutoff_hz']
            rendered,oracle={},{}
            stats={}
            for name,audio in dict(full=full,**parts).items():
                rendered[name]=render_positions(audio,0,positions,cutoff)
                oracle[name]=render_positions(audio,0,oracle_positions,cutoff)
                measured=measure(rendered[name],cycle,case['root_hz'],plan)
                ideal=measure(oracle[name],cycle,case['root_hz'],plan)
                stats[name]={key:dict(**compare(ideal[key],measured[key]),
                    oracle_power_LR=ideal[key][0].tolist(),measured_power_LR=measured[key][0].tolist()) for key in measured}
                for key in measured:
                    # A ratio to an absent component band is not an energy-loss
                    # claim. Keep raw old metrics, and label diagnostic support.
                    support=np.max(ideal[key][0],axis=1)>=max(float(ideal[key][0].max())*1e-8,1e-20)
                    stats[name][key]['oracle_supported_bands']=support.tolist()
                    differences=np.asarray(stats[name][key]['power_difference_db_LR'])
                    stats[name][key]['maximum_supported_band_power_error_db']=float(abs(differences[support]).max()) if support.any() else None
            assert abs(stats['full']['grid']['maximum_band_power_error_db']-item['coherent_oracle']['maximum_band_power_error_db'])<1e-12
            assert abs(stats['full']['total']['maximum_band_power_error_db']-item['oracle']['maximum_band_power_error_db'])<1e-12
            error=float(np.max(abs(sum(rendered[name] for name in parts)-rendered['full'])))
            assert error<=task['linearity_tolerance_fs']
            residue=phase_residue(positions,t,phase,cycle)
            output.update(rendered_component_reconstruction_error_fs=error,components=stats,
                **residue_summary(positions,t,phase,frequency,cycle))
            output['known_high_carriers']=[]
            for order,source in high_carriers(phase,frequency).items():
                resampled=render_positions(source,0,positions,cutoff)
                ideal=render_positions(source,0,oracle_positions,cutoff)
                direct_phase=np.interp(positions,t,phase)
                ideal_phase=np.interp(oracle_positions,t,phase)
                def direct(value):
                    angle=2*np.pi*order*value+.19*order
                    return np.column_stack((.008*np.cos(angle),.006*np.cos(angle+.3)))
                measured_db=10*np.log10(line_power(resampled,cycle,order)/line_power(ideal,cycle,order))
                predicted_db=10*np.log10(line_power(direct(direct_phase),cycle,order)/line_power(direct(ideal_phase),cycle,order))
                output['known_high_carriers'].append(dict(order=order,
                    measured_central_line_difference_db_LR=measured_db.tolist(),
                    independently_predicted_difference_db_LR=predicted_db.tolist(),
                    prediction_error_db=float(abs(measured_db-predicted_db).max())))
            np.savez_compressed(directory/'phase_residue.npz',seconds=positions,residual_cycles=residue)
            axes[0,0].plot(positions[::64],residue[::64]*1e3,label=case_id.replace('fifth_',''))
            color=plt.get_cmap('tab10')(len(report['cases']))
            for column,name in enumerate(('full','common_phase_family','fixed_hz_detail','known_noise')):
                value=stats[name]['grid']['power_difference_db_LR'][-1][0]
                axes[0,1].bar(column+(len(report['cases'])-1)*.23,value,width=.23,color=color,
                    label=case_id.replace('fifth_','') if column==0 else None)
        path=load(frozen/case_id/'coarse.json')
        times=np.array([row['seconds'] for row in path['rows']])
        roots=np.array([row['root_hz'] for row in path['rows']])
        normalized,trace_positions,cutoff=warp(full,0,times,roots,*plan['selected_seconds'],plan['coordinate'])
        output['passes']=[]
        output['initial_residue']=residue_summary(trace_positions,t,phase,frequency,cycle)
        for number in range(plan['phase']['refinement_passes']):
            observation=aperture(normalized,trace_positions,t,phase,plan['coordinate'],plan['phase'])
            np.savez_compressed(directory/f'pass{number+1}_aperture.npz',**{key:value for key,value in observation.items() if key!='rows'})
            entry=dict(pass_number=number+1,aperture=observation['rows'])
            if item['status']!='measured':
                axes[1,0].plot(observation['source_seconds'],observation['point_residual_cycles']-np.median(observation['point_residual_cycles']),label=f'before pass{number+1}')
                if number==0:
                    for column,order in enumerate(observation['orders']):
                        axes[1,1].plot(observation['source_seconds'],observation['aperture_bias_cycles'][:,column],label=str(order))
            try:
                normalized,trace_positions,evidence=refine_once(full,0,normalized,trace_positions,cutoff,plan['coordinate'],plan['phase'])
                cutoff=evidence['source_cutoff_hz']
                entry.update(status='measured',evidence=evidence,residue=residue_summary(trace_positions,t,phase,frequency,cycle))
            except ValueError as exc:
                entry.update(status='rejected',reason=str(exc))
                output['passes'].append(entry)
                break
            output['passes'].append(entry)
        if item['status']=='measured':
            assert np.array_equal(trace_positions,positions), 'Frozen successful coordinate not reproduced'
            output['frozen_final_coordinate_exact']=True
        else:
            assert output['passes'][-1]['status']=='rejected', 'Frozen rapid failure was not reproduced'
        report['cases'].append(output)
        save(directory/'report.json',output)
        print(json.dumps(dict(case=case_id,status=output['frozen_status'],
            family_grid_error=output.get('components',{}).get('common_phase_family',{}).get('grid',{}).get('maximum_band_power_error_db'),
            phase_p95_us=output.get('time_residue_p95_us'),pass_status=[row['status'] for row in output.get('passes',[])])),flush=True)
    axes[0,0].set(title='Frozen coordinate: known common-phase error',xlabel='Source seconds',ylabel='Residual (millicycles)')
    axes[0,1].set(title='8-14 kHz grid capture, L (same frozen coordinate)',ylabel='Estimated / oracle (dB)',xticks=range(4),xticklabels=['Full mixture','Common family','Fixed-Hz detail','Known noise'])
    axes[1,0].set(title='Rapid corner: point residual before each pass',xlabel='Source seconds',ylabel='Cycles',xlim=(1.3,2.5))
    axes[1,1].set(title='Rapid corner: aperture bias before pass1',xlabel='Source seconds',ylabel='Cycles',xlim=(1.3,2.5))
    for axis in axes.flat:
        axis.legend(fontsize=7)
        axis.grid(alpha=.2)
    figure.savefig(args.out/'component_and_aperture.png',dpi=160)
    plt.close(figure)
    report['result']='diagnostic_complete_no_qualification'
finally:
    save(args.out/'report.json',report)

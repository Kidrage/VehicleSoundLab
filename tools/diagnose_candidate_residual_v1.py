"""Independent model reconstruction of fixed-basis screen versus joint fits."""
import argparse
import math
import shutil
import sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','input','audit','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args()
repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
from research_archive_v1 import load,save,sha
from native_chirp_audit_v1.wave import near

a.out.mkdir(parents=True,exist_ok=False)
r=dict(result='running',sources={},parent_files={},windows=[],maximum_model_waveform_error=0.,
    new_fits=False,truth_used=False,real_source_read=False)
for name in ['tools/diagnose_candidate_residual_v1.py','tools/research_archive_v1.py','tools/native_chirp_audit_v1/wave.py']:
    dest=a.out/'exact_sources'/name
    dest.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(repo/name,dest)
    r['sources'][name]=sha(repo/name)


def waveform(row,z):
    t=(np.arange(12000)-6000)/48000
    output=np.zeros((12000,2))
    for line in row['lines']:
        phase=math.tau*(line['frequency_hz']*t+line['chirp_hz_per_second']*t*t/2+line['curvature_hz_per_second2']*t**3/6)
        for channel in range(2):output[:,channel]+=line['amplitude_LR'][channel]*np.cos(phase+line['phase_at_midpoint_LR'][channel])
    output+=row['DC_LR']
    r['maximum_model_waveform_error']=max(r['maximum_model_waveform_error'],near(output,z['reconstructed'],2e-12),
        near(z['audio']-output,z['residual'],2e-12))
    return output


def relative(audio,output):
    w=np.sqrt(np.hanning(12001)[:-1]/12000)
    return np.linalg.norm(w[:,None]*(audio-output),axis=0)/np.linalg.norm(w[:,None]*audio,axis=0)


try:
    audit=load(a.audit/'report.json')
    assert audit['result']=='all12_prerequisite_screen_false_negative_inputs_raw_accepted_nulls_graphs_scores_verified'
    assert audit['input_report_sha256']==sha(a.input/'report.json') and audit['qualified'] is False
    baseline=a.workspace/'baselines/candidate_presence_v1'
    table={v['path']:v['sha256'] for v in load(baseline/'manifest.json')['files']}
    source=baseline/'evidence/observe1/cubic_control'
    def parent(path):
        name=path.relative_to(baseline).as_posix()
        assert sha(path)==table[name]
        r['parent_files'][name]=table[name]
        return path
    folder=a.input/'cubic_control'
    native=load(folder/'native_fits.json')
    joint=load(parent(source/'raw_fits.json'))
    screens=load(folder/'screens.json')
    for i in range(12):
        nz=np.load(parent(source/f'native_{i:02d}.npz'))
        jz=np.load(parent(source/f'tile_{i:02d}.npz'))
        audio=nz['audio']
        near(audio,jz['audio'],0)
        native_wave=waveform(native[i],nz)
        joint_wave=waveform(joint[i],jz)
        native_relative=relative(audio,native_wave)
        joint_relative=relative(audio,joint_wave)
        near(native_relative,native[i]['weighted_relative_residual_LR'])
        near(joint_relative,joint[i]['weighted_relative_residual_LR'])
        item=dict(window=i,native_modes=len(native[i]['lines']),joint_modes=len(joint[i]['lines']),
            native_weighted_relative_LR=native_relative.tolist(),joint_weighted_relative_LR=joint_relative.tolist(),
            screen_fixed_weighted_relative_LR=None,common_native_nonlinear_changes=[])
        sz=np.load(folder/f'screen_{i:02d}.npz')
        if 'coefficients' in sz:
            t=(np.arange(12000)-6000)/48000
            params=np.array([[v['frequency_hz'],v['chirp_hz_per_second'],v['curvature_hz_per_second2']] for v in native[i]['lines']])
            params=np.vstack((params,sz['forecast_parameters']))
            M=len(params)
            angles=math.tau*(t[:,None]*params[:,0]+t[:,None]**2*params[:,1]/2+t[:,None]**3*params[:,2]/6)
            carriers=np.exp(1j*angles)
            co=sz['coefficients']
            output=(carriers@(co[:M]-1j*co[M:2*M])).real+co[-1]
            rel=relative(audio,output)
            item['screen_fixed_weighted_relative_LR']=rel.tolist()
            w=np.sqrt(np.hanning(12001)[:-1]/12000)
            cost=np.sum((w[:,None]*(audio-output))**2,axis=0)
            near(cost,screens[i]['full_cost_LR'],1e-12)
            near(rel,np.sqrt(np.array(screens[i]['full_cost_LR'])/np.sum((w[:,None]*audio)**2,axis=0)),1e-10)
        for v in native[i]['lines']:
            counterpart=next(u for u in joint[i]['lines'] if u['nominal_hz']==v['nominal_hz'])
            item['common_native_nonlinear_changes'].append(dict(nominal_hz=v['nominal_hz'],
                frequency_change_hz=counterpart['frequency_hz']-v['frequency_hz'],
                rate_change_hzs=counterpart['chirp_hz_per_second']-v['chirp_hz_per_second'],
                curvature_change_hzs2=counterpart['curvature_hz_per_second2']-v['curvature_hz_per_second2']))
        r['windows'].append(item)
    r.update(result='all12_fixed_native_screen_and_frozen_joint_models_independently_reconstructed',
        input_report_sha256=sha(a.input/'report.json'),audit_report_sha256=sha(a.audit/'report.json'),
        comparison_is_known_prerequisite_only=True,not_a_new_selection_rule_or_fullqualification=True)
except Exception as exc:
    r.update(result='failed',error=repr(exc))
    raise
finally:save(a.out/'report.json',r)
print(dict(result=r['result'],last3=r['windows'][-3:],maximum_waveform_error=r['maximum_model_waveform_error']))

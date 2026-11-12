"""Bind stationary rejections, known controls and metadata-only proposal."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--out',type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from drive_evidence_v1.sources import sha

a.out.mkdir(parents=True,exist_ok=False)
base=a.workspace/'references/analysis/B_stationary_dna_v1'
r=dict(schema='vsl.B-stationary-dna-publication/1',result='running',reports={},sources={})
try:
    names=['explore1','qualify1','probes1','validate1','fit1','inspect1','post_action_qualify1',
           'post_action_fit1','C_controls1','register1']
    for name in names:
        path=base/name/'report.json'
        r['reports'][name]=dict(path=path.relative_to(a.workspace).as_posix(),sha256=sha(path))
    validation=json.loads((base/'validate1/report.json').read_text(encoding='utf-8'))
    assert validation['result']=='passed'
    c_controls=json.loads((base/'C_controls1/report.json').read_text(encoding='utf-8'))
    assert c_controls['result'] in ('passed','rejected')
    real=[]
    for directory in ('fit1','post_action_fit1'):
        data=json.loads((base/directory/'report.json').read_text(encoding='utf-8'))
        assert data['result']=='measured'
        for name,case in data['cases'].items():
            assert not case['stationary_scope_passed'] and case['candidate'] is None
            real.append(dict(id=name,root_hz=case['acoustic_root_hz'],
                maximum_heldout_db=case['maximum_heldout_power_difference_db'],
                maximum_heldout_correlation=case['maximum_heldout_correlation_difference'],
                independent_halves=case['independent_halves'],model_exported=False))
    files=subprocess.check_output(['git','ls-files'],cwd=repo,text=True).splitlines()
    c_files=[name for name in files if Path(name).suffix.lower() in ('.c','.h')]
    assert len(c_files)==530
    subprocess.run(['git','diff','--exit-code','HEAD','--','src','modules','experiments','voices'],cwd=repo,check=True,capture_output=True)
    c_hashes={name:sha(repo/name) for name in c_files}
    assert sha(repo/'references/segments_v1.json')==sha(a.workspace/'references/segments_v1.json')
    (a.out/'C_files_sha256.json').write_text(json.dumps(c_hashes,indent=2)+'\n',encoding='utf-8')
    sources=[Path(__file__),*repo.glob('research/B_stationary*.json'),
             repo/'research/怠速与加速补充素材V2.md',repo/'research/B驻车声纹验证V1.md',
             repo/'references/segments_v1.json']
    sources+=list((repo/'tools/stationary_dna_v1').glob('*.py'))
    for pattern in ('*B_stationary*.py','*idle_sources_v1.py','*idle_candidates_v2.py','*stationary_profile_v1.py'):
        sources+=list((repo/'tools').glob(pattern))
    for source in sources:
        relative=source.relative_to(repo);target=a.out/'exact_sources'/relative
        target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
        r['sources'][relative.as_posix()]=sha(source)
    # Original, unchanged stereo short-window band powers. Annotations are
    # contextual video observations, not calibrated combustion timestamps.
    fig,axes=plt.subplots(2,1,figsize=(12,7),constrained_layout=True)
    observed=a.workspace/'references/analysis/cabin_low_v1/target_observe1'
    for axis,case,limits,spans in [
        (axes[0],'park_before_departure',(130,138),[(130.5,131.6,'ANIMA control'),(132.5,135.1,'Head / console')]),
        (axes[1],'arrival_park',(799,808),[(801.5,805,'Head / console'),(805.5,807.1,'Start-stop / logo')])]:
        with np.load(observed/case/'observations.npz',allow_pickle=False) as z:
            seconds=z['seconds'];power=z['power_LR']
        for index,label in [(1,'120-400 Hz'),(4,'3-8 kHz'),(5,'8-16 kHz')]:
            db=10*np.log10(np.maximum(power[:,index].mean(axis=0),1e-30))
            axis.plot(seconds,db,label=label,linewidth=1)
        for lo,hi,label in spans:
            axis.axvspan(lo,hi,color='gray',alpha=.1)
            axis.text((lo+hi)/2,.98,label,ha='center',va='top',transform=axis.get_xaxis_transform(),fontsize=9)
        axis.set(xlim=limits,ylabel='Original stereo mean band power (dBFS)',xlabel='Local MP3 seconds')
        axis.grid(alpha=.2);axis.legend(loc='lower left',ncol=3)
    fig.suptitle('B source context: changing actions and recorded band powers\nShaded video actions are approximate context, not fuel/RPM/physical-source labels')
    fig.savefig(a.out/'recorded_bands_and_actions.png',dpi=140);plt.close(fig)
    search=a.workspace/'references/analysis/idle_source_candidates_v2/search1'
    watch=a.workspace/'references/analysis/idle_source_candidates_v2/watch1'
    candidates=json.loads((watch/'report.json').read_text(encoding='utf-8'))
    assert not candidates['media_downloaded']
    assert candidates['search_report_sha256']==sha(search/'report.json')
    for item in candidates['candidates']:
        assert item['result']=='metadata_only' and item['playability']=='OK'
        assert not any(item[k] for k in ('approved','media_downloaded','local_audio_review','local_visual_review'))
        assert sha(watch/item['source_page'])==item['page_sha256']
    r.update(result='qualified_controls_real_sources_rejected',real_cases=real,
        analytic_positive_controls=6,analytic_negative_controls=6,
        maximum_analytic_oracle_power_error_db=max(v['maximum_oracle_band_power_error_db'] for v in validation['cases'] if v['positive_control']),
        C_fixture_result=c_controls['result'],C_fixture_report_sha256=sha(base/'C_controls1/report.json'),
        C_files=530,C_files_hashes_sha256=sha(a.out/'C_files_sha256.json'),
        source_plot_sha256=sha(a.out/'recorded_bands_and_actions.png'),
        candidate_watch_report_sha256=sha(watch/'report.json'),
        candidate_search_report_sha256=sha(search/'report.json'),
        candidates=[{k:v[k] for k in ('id','url','title','channel','seconds','approved','media_downloaded')} for v in candidates['candidates']],
        no_new_vehicle_model=True,no_runtime_change=True,no_default_change=True,
        generic_phase_qualification='not_passed_unchanged',idle_acceleration_complete=False,
        moving35='held_unchanged',original_idle_question='pending_not_duplicated')
    summary=repo/'research/B_stationary_dna_v1_summary.json'
    assert not summary.exists()
    summary.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
except Exception as exc:
    r.update(result='failed',error=repr(exc));raise
finally:
    (a.out/'report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(result=r['result'],C_fixture_result=r['C_fixture_result'],real_profiles_exported=0)),flush=True)

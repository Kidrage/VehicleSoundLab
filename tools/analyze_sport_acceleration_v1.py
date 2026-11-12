"""Separate a newly inspected Sport run into context and acoustic eligibility."""
import argparse
import csv
import json
from pathlib import Path
import shutil
import sys

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--out',type=Path,required=True)
a = p.parse_args()
repo = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from drive_evidence_v1.sources import read,sha
from shift_evidence_v1.spectrum import observe,region_stats,BANDS
from local_voice_v1.qualification import qualify
from acceleration_passage_v1.diagnostics import controls

a.out.mkdir(parents=True,exist_ok=False)
r = dict(schema='vsl.sport-acceleration-analysis/1',result='running',source_sha256={},input_sha256={})
try:
    plan_path = repo/'research/sport_acceleration_v1_plan.json'
    plan = json.loads(plan_path.read_text(encoding='utf-8'))
    paths = [Path(__file__),plan_path,repo/'research/sport_acceleration_v1_annotations.json',
        repo/'tools/local_voice_v1/qualification.py',repo/'tools/drive_evidence_v1/sources.py',
        repo/'tools/shift_evidence_v1/spectrum.py',repo/'tools/state_colour_v2/clock.py',
        repo/'tools/state_dna_v1/compare.py',repo/'tools/phase_clock_v1/projection.py',
        repo/'tools/exterior_clock_v1/warp.py',repo/'tools/sound_dna/windowed.py',
        repo/'tools/acceleration_passage_v1/diagnostics.py']
    for path in paths:
        name = path.relative_to(repo)
        target = a.out/'exact_sources'/name
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,target)
        r['source_sha256'][name.as_posix()] = sha(path)
    root = a.workspace/'references/analysis/sport_acceleration_v1'
    count = 0
    for folder in ('inspect1','inspect2'):
        directory = root/folder
        context = json.loads((directory/'report.json').read_text(encoding='utf-8'))
        assert context['result'] == 'frames_decoded_not_yet_human_annotated'
        assert sha(directory/'executed_inspect.py') == context['source_sha256']
        assert sha(directory/'executed_plan.json') == context['inspection_plan_sha256']
        r['input_sha256'][str(directory/'report.json')] = sha(directory/'report.json')
        for source in context['sources'].values():
            assert sha(Path(source['video'])) == source['video_sha256']
            r['input_sha256'][source['video']] = source['video_sha256']
            for row in source['frames']+source['boards']:
                assert sha(directory/'E'/row['file']) == row['sha256']
            count += len(source['frames'])
    annotation = json.loads((repo/'research/sport_acceleration_v1_annotations.json').read_text(encoding='utf-8'))
    r['annotations'] = annotation
    r['plan'] = plan
    audio,provenance = read(a.workspace,plan['source_segment'],plan['source_use'])
    r['provenance'] = provenance
    r['controls'] = controls()
    observed = observe(audio,provenance['seconds'][0],80)
    directory = a.out/'low_case'
    directory.mkdir()
    r['low_case'] = qualify(audio,provenance['seconds'][0],observed,plan['low_case'],plan,directory)
    r['raw_budgets'] = []
    for lo,hi in plan['raw_budget_intervals_seconds']:
        stats = region_stats(observed,lo+.04,hi-.04)
        assert stats is not None
        r['raw_budgets'].append(dict(source_seconds=[lo,hi],**stats))
    sf.write(a.out/'low_raw_reference.wav',audio[round((58.6-58)*48000):round((59.6-58)*48000)],48000,subtype='FLOAT')
    with (repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig') as f:
        c_index = list(csv.DictReader(f))
    assert len(c_index) >= 478
    for row in c_index:
        assert sha(repo/row['文件']) == row['SHA-256'],row['文件']
    fig,axes = plt.subplots(3,1,figsize=(11,9),sharex=True,constrained_layout=True)
    keep = (observed['seconds']>=58)&(observed['seconds']<=68)
    power = 10*np.log10(np.maximum(observed['power_low'][:,keep],1e-30))
    axes[0].pcolormesh(observed['seconds'][keep],observed['hz'],power,
        vmin=power.max()-55,vmax=power.max(),cmap='magma',shading='auto',rasterized=True)
    axes[0].set(ylabel='Observed Hz',ylim=(35,900),title='E Sport: separate gentle rise, downshifts and loaded-rise contexts')
    for i,(lo,hi) in enumerate(BANDS):
        axes[1].plot(observed['seconds'][keep],10*np.log10(np.maximum(observed['power_LR'][:,i,keep].mean(axis=0),1e-30)),label=f'{lo}-{hi}Hz')
    axes[1].set(ylabel='Raw band dBFS')
    axes[1].legend(ncol=3,fontsize=8)
    labels = annotation['speed_observations']
    axes[2].plot([v['seconds'] for v in labels],[v['dash_kmh'] for v in labels],'o-',label='Displayed dash km/h')
    axes[2].plot([v['seconds'] for v in labels],[v['phone_kmh'] for v in labels],'o-',label='Displayed phone km/h')
    axes[2].set(ylabel='Displayed km/h',xlabel='Original media seconds; A/V/display/phone latency unknown')
    axes[2].legend(fontsize=8)
    for ax in axes:
        for boundary in annotation['display_changes']:
            ax.axvspan(boundary['last_old_seconds'],boundary['first_new_seconds'],color='gray',alpha=.15)
    fig.savefig(a.out/'context.png',dpi=140)
    plt.close(fig)
    r.update(result='context_and_local_diagnostic_observed',frames_inspected=count,C_H_index_verified=len(c_index),
        Ctests_not_repeated=47,new_model=False,new_C=False,new_timbre=False,runtime_changed=False,
        limits=['Sport versus Corsa are different runs/layouts and recording conditions, not matched load trials',
            'Local phase diagnostics cannot promote generic phase_clock_v1, which remains not_passed',
            'No extra method/reference/anchor/window search on failure; no model exported',
            'Raw absolute bands and common46.875Hz harmonic colour use different coordinates',
            'Stereo observations are not engine banks or physical speakers',
            'Frame/video PTS and gear animation brackets are not clutch/cut/fueling timestamps',
            'No new listening question, native/device/longrun/spatial validation or replacement of moving35/idle candidates'])
except Exception as exc:
    r.update(result='failed',error=repr(exc))
    raise
finally:
    (a.out/'report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(result=r['result'],frames=r['frames_inspected'],low_gate=r['low_case']['local_diagnostic_gate'],
    paths={k:v['status'] for k,v in r['low_case']['references'].items()},comparisons=r['low_case']['comparisons'])))

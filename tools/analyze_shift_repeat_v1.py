"""Compare two newly observed shifts against a separate approved Corsa passage."""
import argparse
import json
from pathlib import Path
import shutil
import sys
import urllib.request

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True)
parser.add_argument('--out',type=Path,required=True)
args=parser.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
from scipy import signal
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from drive_evidence_v1.sources import read,sha
from shift_evidence_v1.spectrum import observe,region_stats,BANDS,RELATIVE_BANDS
from shift_evidence_v1.timing import descent

args.out.mkdir(parents=True,exist_ok=False)
exploration_path=args.workspace/'references/analysis/shift_repeat_v1/exploration1/report.json'
exploration=json.loads(exploration_path.read_text(encoding='utf-8'))
audio,provenance=read(args.workspace,'E_corsa_first_context','cabin_dynamic_observation')
assert provenance==exploration['provenance']
for row in exploration['frames']:
    assert sha(exploration_path.parent/row['file'])==row['sha256']
annotation_path=repo/'research/shift_repeat_v1_annotations.json'
annotation=json.loads(annotation_path.read_text(encoding='utf-8'))
family=next(f for f in exploration['families'] if f['start']==48 and f['anchor_root']==45)
alternate=next(f for f in exploration['families'] if f['start']==48.5 and f['anchor_root']==35)
ft=np.array([r['seconds'] for r in family['rows']]);ff=np.array([r['reference_hz'] for r in family['rows']])
other={r['seconds']:r['reference_hz'] for r in alternate['rows']}
common=[r for r in family['rows'] if r['seconds'] in other]
alternative_error=max(abs(r['reference_hz']-other[r['seconds']]) for r in common)
assert alternative_error==0

def change(observed,at):
    before=region_stats(observed,at-.20,at-.10);after=region_stats(observed,at+.10,at+.20)
    pre,post=np.array(before['power_LR']),np.array(after['power_LR'])
    return dict(before=before,after=after,
                power_change_db_LR=(10*np.log10(post/pre)).tolist(),
                power_change_db= (10*np.log10(post.mean(axis=0)/pre.mean(axis=0))).tolist())

analyses=[]
for ms in (80,60,40):
    observed=observe(audio,47,ms,clock=(ft,ff))
    relative=dict(observed,power_LR=observed['relative_power_LR'],cross_LR=observed['relative_cross_LR'])
    events=[]
    for label in annotation['gear_display_changes']:
        event=descent(ft,ff,label['last_old_seconds']-.7,label['first_new_seconds']+.1)
        at=event['marker_seconds']
        event.update(display=label,fixed=change(observed,at),relative=change(relative,at))
        events.append(event)
    analyses.append(dict(window_ms=ms,clock='Same independently chosen80ms observed family for all band comparisons',events=events))
    np.savez_compressed(args.out/f'window_{ms}.npz',seconds=observed['seconds'],power=observed['power_LR'],
                        relative_power=observed['relative_power_LR'],cross=observed['cross_LR'])

old_root=args.workspace/'baselines/shift_evidence_v1'
manifest=json.loads((old_root/'manifest.json').read_text(encoding='utf-8'))
old_summary=old_root/'docs/shift_evidence_v1_summary.json'
assert sha(old_summary)==next(r['sha256'] for r in manifest['files'] if r['path']=='docs/shift_evidence_v1_summary.json')
old=json.loads(old_summary.read_text(encoding='utf-8'))
assert old['provenance']['master_sha256']==provenance['master_sha256']
old_colour=np.array([r['relative_band_power_change_db'] for r in old['events']])
new_colour=np.array([r['relative']['power_change_db'] for r in analyses[0]['events']])
# Midband6.5..18.5 is an explicit reference, not a pure engine source. A dB
# difference relative to it removes common gain but not speed/gear/path effects.
old_shape=old_colour[:,3:5]-old_colour[:,2,None]
new_shape=new_colour[:,3:5]-new_colour[:,2,None]
prediction=np.median(old_shape,axis=0);heldout=new_shape-prediction
same_gears=new_shape-old_shape[:2]

# Validate comparison mechanics using known changing pitch and independently
# specified time-varying gain. These fixtures do not identify real pedal/load.
times=np.arange(len(audio))/48000+47
roots=np.interp(times,ft,ff)/5
phase=2*np.pi*np.cumsum(roots)/48000
partials=np.arange(1,131);amplitude=.012/np.sqrt(partials)
def fixture(colour=False):
    result=np.zeros((len(audio),2))
    # Known broad shape changes at acoustic markers, evaluated in the same
    # before/after windows. The high orders receive-6.0206dB, mid-3.0103dB.
    commands=np.zeros(len(times))
    for event in analyses[0]['events']:
        at=event['marker_seconds'];commands=np.maximum(commands,((times>=at+.04)&(times<at+.25)).astype(float))
    gain=.65+.30*np.sin(2*np.pi*.8*(times-47))**2
    for h,a in zip(partials,amplitude):
        shape=1
        if colour:
            target=.5 if h>=46 else np.sqrt(.5) if h>=19 else 1
            shape=1+commands*(target-1)
        result[:,0]+=gain*a*shape*np.cos(h*phase+h*.17)
        result[:,1]+=gain*a*.8*shape*np.cos(h*phase+h*.17+.2)
    return result
controls=[]
for changed in (False,True):
    control_audio=fixture(changed)
    obs=observe(control_audio,47,80,clock=(ft,ff))
    rel=dict(obs,power_LR=obs['relative_power_LR'],cross_LR=obs['relative_cross_LR'])
    rows=[]
    for event in analyses[0]['events']:
        db=np.array(change(rel,event['marker_seconds'])['power_change_db'])
        shape=db[3:5]-db[2]
        expected=np.array([-3.010299956639812,-6.020599913279624]) if changed else np.zeros(2)
        rows.append(dict(marker=event['marker_seconds'],measured_shape_db=shape.tolist(),expected_db=expected.tolist(),
                         max_error_db=float(abs(shape-expected).max())))
    controls.append(dict(shape_changed=changed,rows=rows))

# Exact/regained copies are recognised at unity despite a changed overall gain.
x=signal.resample_poly(audio[:48000],1,12,axis=0)
control_correlations=[]
for c in range(2):
    a=x[:,c]-x[:,c].mean();b=.37*x[:,c]+.01;b-=b.mean()
    control_correlations.append(float(np.dot(a,b)/np.sqrt(np.dot(a,a)*np.dot(b,b))))
assert min(control_correlations)>1-1e-12

upstream_revision='ac2b37d8639027d79934a2023cf8d1d37d3b2f96'
upstream=[]
for name in ('patchers/v10_state_renderer~.maxpat','patchers/v10_sound_dna~.maxpat','VehicleSoundSynth-V6.maxproj'):
    request='https://raw.githubusercontent.com/Kidrage/VehicleSoundSynth/'+upstream_revision+'/'+name
    data=urllib.request.urlopen(request,timeout=30).read()
    path=args.out/'upstream'/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
    upstream.append(dict(path=name,sha256=sha(path),bytes=len(data)))

fig,axes=plt.subplots(1,2,figsize=(11,4.5),constrained_layout=True)
for i,(name,shape) in enumerate((('Earlier5',old_shape),('First2',new_shape))):
    for b in range(2):
        axes[b].scatter(np.full(len(shape),i),shape[:,b],label=name)
        axes[b].plot([i-.13,i+.13],[np.median(shape[:,b])]*2,color='black')
for b in range(2):
    axes[b].set_xticks([0,1],['82..94s /5shifts','49..52s /2shifts'])
    axes[b].set_ylabel('Post/pre shape dB, relative to6.5..18.5')
    axes[b].set_title(['18.5..45.5 x root','45.5..110.5 x root'][b]);axes[b].axhline(0,color='grey',lw=.8)
fig.savefig(args.out/'passage_comparison.png',dpi=150);plt.close(fig)
report=dict(schema='vsl.shift-repeat-analysis/1',provenance=provenance,annotation_sha256=sha(annotation_path),
    exploration_sha256=sha(exploration_path),independently_started_family_common_error_hz=alternative_error,
    old_manifest_sha256=sha(old_root/'manifest.json'),old_summary_sha256=sha(old_summary),
    band_hz=BANDS,relative_bands=RELATIVE_BANDS,analyses=analyses,
    old_shape_db=old_shape.tolist(),new_shape_db=new_shape.tolist(),old_median_prediction_db=prediction.tolist(),
    heldout_first_passage_error_db=heldout.tolist(),same_gear_pair_difference_db=same_gears.tolist(),
    known_controls=controls,duplicate_gain_control_correlation=control_correlations,
    upstream_revision=upstream_revision,upstream_text=upstream,runtime_changed=False,human_accepted=False,
    limits=['Acoustic shape observations, no independently measured torque/pedal/load/fueling',
            'Only two passages of one recording; launch traction/gear/speed/path can differ',
            'First and second passages share presentation but waveform correlation is low; no claim of ECU-independent trials',
            'Short-window variants share one80ms clock; not independent clock estimates',
            'No target promoted from a median or one successful known fixture'])
sources=[Path(__file__),repo/'research/shift_repeat_v1_annotations.json',repo/'tools/explore_shift_repeat_v1.py',
         repo/'tools/drive_evidence_v1/sources.py',repo/'tools/drive_evidence_v1/family.py',
         repo/'tools/shift_evidence_v1/spectrum.py',repo/'tools/shift_evidence_v1/timing.py']
report['source_sha256']={p.relative_to(repo).as_posix():sha(p) for p in sources}
for p in sources:
    dest=args.out/'exact_sources'/p.relative_to(repo);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
(args.out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(markers=[e['marker_seconds'] for e in analyses[0]['events']],old_shape=old_shape.tolist(),
    new_shape=new_shape.tolist(),heldout_error=heldout.tolist(),control_errors=[[r['max_error_db'] for r in c['rows']] for c in controls]),ensure_ascii=False))

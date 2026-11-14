"""Probe a frozen window law on existing phase streams; generates no gain or audio."""
import argparse,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','input','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
from scipy.interpolate import CubicSpline
from research_archive_v1 import load,save,sha
from idle_amp_phase_link_v1.observe import predict

a.out.mkdir(parents=True,exist_ok=False)
r=dict(result='running',sources={},inputs={},streams=[])
def track(path):r['inputs'][str(path)]=sha(path);return path
try:
    for name in ['tools/probe_idle_amp_phase_stream_v1.py','tools/idle_amp_phase_link_v1/observe.py',
        'research/idle_amp_phase_link_v1_stream_plan.json','tools/research_archive_v1.py']:
        dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,dest)
        r['sources'][name]=sha(repo/name)
    source=load(track(a.input/'report.json'));model=source['models']['source'];assert model['available']
    parts={}
    for row in source['cases']:
        if row['metadata']['kind']!='source':continue
        with np.load(track(a.input/row['file'])) as f:parts[row['metadata']['part']]=(f['x'],f['y'])
    x,y=parts['train'];lower=x.min(axis=0);upper=x.max(axis=0)
    b=np.array(model['coefficients'])[1:]/np.array(model['std'])[:,None]
    c=np.array(model['coefficients'])[0]-np.array(model['mean'])@b
    radius=np.hypot(b[0],b[2])+np.hypot(b[1],b[3])
    r['global_observed_window_log_bounds']=[(c-radius).tolist(),(c+radius).tolist()]
    r['source_observed_log_ranges']={key:[value[1].min(axis=0).tolist(),value[1].max(axis=0).tolist()] for key,value in parts.items()}
    r['source_TRAIN_feature_box']=[lower.tolist(),upper.tolist()]
    phase=a.workspace/'baselines/idle_phase_recipe_v1/evidence/render2'
    prior=load(track(phase/'report.json'));phase_model=load(track(phase/'model.json'));assert phase_model['node_rate']==200
    assert [(row['seed'],row['seconds']) for row in prior['renders']]==[(149921,180),(277139,24),(381611,24)]
    weight=.5-.5*np.cos(2*np.pi*np.arange(9600)/9600);weight/=weight.sum()
    for row in prior['renders']:
        file=track(phase/row['motion_file']);assert sha(file)==row['motion_sha256']
        with np.load(file) as f:coords=f['coordinate_nodes']
        motion=CubicSpline((np.arange(len(coords))-2)/200,coords,bc_type='natural')
        frames=int(row['seconds']*48000);starts=np.arange(12000,frames-12000-9600+1,960)
        # Process one bounded chunk at a time; every full window is still native48k.
        features=[]
        for first in range(0,len(starts),128):
            batch=starts[first:first+128];lo=int(batch[0]);hi=int(batch[-1]+9600)
            u=motion(np.arange(lo,hi)/48000);w=np.exp(1j*u)
            f=np.array([weight@w[j-lo:j-lo+9600] for j in batch])
            features.append(np.column_stack((f.real,f.imag)))
        features=np.concatenate(features);prediction=predict(model,features)
        assert np.all(prediction>=c-radius-1e-12) and np.all(prediction<=c+radius+1e-12)
        dest=a.out/('stream_'+str(row['seed'])+'.npz')
        np.savez_compressed(dest,starts=starts,features=features,predicted_window_log_magnitude=prediction)
        r['streams'].append(dict(seed=row['seed'],seconds=row['seconds'],windows=len(starts),
            file=dest.name,sha256=sha(dest),phase_nodes_input=str(file),phase_nodes_sha256=sha(file),
            predicted_window_log_range=[prediction.min(axis=0).tolist(),prediction.max(axis=0).tolist()],
            predicted_log_offset_from_TRAIN_mean_range=[(prediction-y.mean(axis=0)).min(axis=0).tolist(),(prediction-y.mean(axis=0)).max(axis=0).tolist()],
            per_feature_outside_TRAIN_box_fraction=np.mean((features<lower)|(features>upper),axis=0).tolist(),
            any_feature_outside_TRAIN_box_fraction=float(np.mean(np.any((features<lower)|(features>upper),axis=1)))))
        print(dict(seed=row['seed'],windows=len(starts),prediction_range=r['streams'][-1]['predicted_window_log_range']),flush=True)
    r.update(result='existing_full_phase_streams_window_law_probed',source_model_refitted=False,
        synthesized_gain_or_audio=False,instantaneous_AM_law_exported=False,runtime_changed=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)

"""Independent native-window interpolation probe and global circular bound audit."""
import argparse,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','source','input','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
from scipy.interpolate import make_interp_spline
from research_archive_v1 import load,save,sha

a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_auditor.py')
r=dict(result='running',source_trajectory_or_audio_generated=False)
try:
    stream=load(a.input/'report.json');source=load(a.source/'report.json')
    assert stream['result']=='existing_full_phase_streams_window_law_probed'
    for path,digest in stream['inputs'].items():assert sha(path)==digest
    for path,digest in stream['sources'].items():assert sha(repo/path)==digest==sha(a.input/'exact_sources'/path)
    model=source['models']['source'];coefficient=np.array(model['coefficients'])
    b=coefficient[1:]/np.array(model['std'])[:,None];base=coefficient[0]-np.array(model['mean'])@b
    radius=np.sqrt(b[0]**2+b[2]**2)+np.sqrt(b[1]**2+b[3]**2)
    bounds=np.array([base-radius,base+radius])
    error=dict(all_native_window_features=0.,all_predictions=0.,all_summary_metrics=0.,global_bounds=0.,extremal_witness=0.,carrier_cancellation=0.)
    error['global_bounds']=float(abs(bounds-stream['global_observed_window_log_bounds']).max())
    for j in range(3):
        psi=np.arctan2(b[2,j],b[0,j]);eta=np.arctan2(b[3,j],b[1,j])
        v=np.array([np.cos(psi),np.cos(eta),np.sin(psi),np.sin(eta)])
        for sign,k in [(-1,0),(1,1)]:error['extremal_witness']=max(error['extremal_witness'],abs(float(base[j]+sign*v@b[:,j])-bounds[k,j]))
    cases={row['metadata']['part']:row for row in source['cases'] if row['metadata']['kind']=='source'}
    with np.load(a.source/cases['train']['file']) as f:low=f['x'].min(axis=0);high=f['x'].max(axis=0);mean_y=f['y'].mean(axis=0)
    weight=np.sin(np.pi*np.arange(9600)/9600)**2;weight/=sum(weight)
    r['streams']=[]
    for row in stream['streams']:
        assert sha(a.input/row['file'])==row['sha256'] and sha(row['phase_nodes_input'])==row['phase_nodes_sha256']
        with np.load(row['phase_nodes_input']) as f:coords=f['coordinate_nodes']
        motion=make_interp_spline((np.arange(len(coords))-2)/200,coords,bc_type='natural')
        with np.load(a.input/row['file']) as f:starts=f['starts'];features=f['features'];prediction=f['predicted_window_log_magnitude']
        expected=np.arange(12000,row['seconds']*48000-21600+1,960);assert np.array_equal(starts,expected)
        checked=[]
        for first in range(0,len(starts),128):
            batch=starts[first:first+128];lo=int(batch[0]);hi=int(batch[-1]+9600)
            u=motion(np.arange(lo,hi)/48000)
            v=np.column_stack((np.cos(u),np.sin(u)))
            checked.append(np.array([weight@v[j-lo:j-lo+9600] for j in batch]))
        checked=np.concatenate(checked)
        pred=np.column_stack((np.ones(len(checked)),(checked-model['mean'])/model['std']))@coefficient
        error['all_native_window_features']=max(error['all_native_window_features'],float(abs(checked-features).max()))
        error['all_predictions']=max(error['all_predictions'],float(abs(pred-prediction).max()))
        for key,v in [('predicted_window_log_range',np.array([pred.min(axis=0),pred.max(axis=0)])),
            ('predicted_log_offset_from_TRAIN_mean_range',np.array([(pred-mean_y).min(axis=0),(pred-mean_y).max(axis=0)])),
            ('per_feature_outside_TRAIN_box_fraction',np.mean((checked<low)|(checked>high),axis=0)),
            ('any_feature_outside_TRAIN_box_fraction',np.mean(np.any((checked<low)|(checked>high),axis=1)))]:
            error['all_summary_metrics']=max(error['all_summary_metrics'],float(abs(v-row[key]).max()))
        assert np.all(pred>=bounds[0]-1e-12) and np.all(pred<=bounds[1]+1e-12)
        # Verify omitted acoustic carrier cancels in the actual relative phasors.
        t=np.linspace(.25,row['seconds']-.25,64);u=motion(t)
        M=np.array([[-1.,-1.,1.],[3.,-2.,0.]]);right=np.linalg.lstsq(M,np.eye(2),rcond=None)[0]
        theta=(2*np.pi*37.5*t)[:,None]*[2.,3.,5.]+u@right.T
        z=np.cos(theta)+1j*np.sin(theta)
        w=np.column_stack((z[:,2]*z[:,1].conj()*z[:,0].conj(),z[:,0]**3*z[:,1].conj()**2))
        error['carrier_cancellation']=max(error['carrier_cancellation'],float(abs(w-np.exp(1j*u)).max()))
        r['streams'].append(dict(seed=row['seed'],seconds=row['seconds'],all_windows=len(starts),all_native_windows_checked=True))
    assert max(v for key,v in error.items() if key!='carrier_cancellation')<1e-10,error
    assert error['carrier_cancellation']<1e-9,error
    r.update(result='passed',errors=error,source_model_refitted=False,new_gain_or_audio=False,
        input_report_sha256=sha(a.input/'report.json'),source_report_sha256=sha(a.source/'report.json'),
        note='All native window predictions are diagnostic observed-window quantities, not instantaneous gain envelopes.')
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(dict(result=r['result'],errors=r.get('errors')),flush=True)

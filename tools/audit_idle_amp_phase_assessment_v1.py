"""Check the posthoc MSE bias/variance accounting without refitting a model."""
import argparse,math,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','input','assessment','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
from research_archive_v1 import load,save,sha
a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_auditor.py')
r=dict(result='running',no_refit=True)
try:
    source=load(a.input/'report.json');assessment=load(a.assessment/'report.json')
    assert assessment['result']=='AM_phase_source_and_stream_evidence_assessed'
    assert assessment['source_report_sha256']==sha(a.input/'report.json')
    base=np.array(source['models']['source']['TRAIN_target_mean']);maximum=0.
    for row in assessment['source_MSE_decomposition']:
        part=row['part'];case=next(v for v in source['cases'] if v['label']=='source_'+part)
        evaluation=next(v for v in source['evaluations'] if v['family']=='source' and v['part']==part)
        with np.load(a.input/case['file']) as f:y=f['y']
        error=np.load(a.input/evaluation['prediction_file'])-y;ref=base-y
        def moments(v):
            mean=np.array([math.fsum(v[:,j])/len(v) for j in range(3)])
            variance=np.array([math.fsum((v[:,j]-mean[j])**2)/len(v) for j in range(3)])
            return mean**2,variance
        bias,variance=moments(error);oldbias,oldvariance=moments(ref)
        for key,value in [('error_variance',variance),('error_squared_bias',bias),
            ('TRAIN_constant_error_variance',oldvariance),('TRAIN_constant_squared_bias',oldbias),
            ('fractional_error_variance_reduction',1-variance/oldvariance)]:
            maximum=max(maximum,float(abs(value-row[key]).max()))
        assert abs(bias+variance-evaluation['MSE']).max()<1e-12
        assert abs(oldbias+oldvariance-evaluation['TRAIN_constant_MSE']).max()<1e-12
    assert maximum<1e-12
    assert sha(a.assessment/assessment['figure']['file'])==assessment['figure']['sha256']
    r.update(result='passed',all2parts3targets_bias_variance_checked=True,maximum_error=maximum,
        assessment_sha256=sha(a.assessment/'report.json'),
        note='CHECK error variance for187Hz is worse despite lower total MSE; no waveform or physical coupling is validated.')
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(dict(result=r['result'],maximum_error=r.get('maximum_error')),flush=True)

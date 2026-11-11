"""Fit one common L/R harmonic-gain shape; validate on held-out passages."""
import argparse,json,sys
from pathlib import Path
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True);parser.add_argument('--analysis',type=Path,required=True);parser.add_argument('--out',type=Path,required=True)
args=parser.parse_args();sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
from scipy.optimize import least_squares,brentq
from drive_evidence_v1.sources import sha
from state_colour_v2.features import shape_delta,HZ,BANDS
CENTERS=np.sqrt(np.array(BANDS)[:,0]*np.array(BANDS)[:,1])/46.875
ORDERS=np.arange(1,289)
def gains(db):return 10**(np.interp(np.log2(ORDERS),np.log2(np.r_[CENTERS,128.,320.]),np.r_[db,0.,0.])/20)
def predicted(db,power):return shape_delta(power,power*gains(db)[:,None]**2).mean(axis=1)
def fit(baselines,targets):
    # Equal passage weight, common stereo gain; remove scalar ambiguity by mean.
    def residual(db):return np.r_[(np.stack([predicted(db,p) for p in baselines])-targets).ravel(),np.mean(db)]
    result=least_squares(residual,np.zeros(5),bounds=(-18,18),xtol=1e-12,ftol=1e-12,gtol=1e-12)
    return result.x
def normalize(db, baselines):
    pooled=np.mean(baselines,axis=0);keep=HZ<6000
    scalar=brentq(lambda shift:np.sum(pooled[keep]*gains(db+shift)[keep,None]**2)-np.sum(pooled[keep]),-24,24)
    return db+scalar,float(scalar)

args.out.mkdir(parents=True,exist_ok=False)
r=json.loads((args.analysis/'report.json').read_text());pairs=r['pairs'];baseline=[];target=[]
for row in pairs:
    baseline.append(np.array(r['cases']['fall'+str(row['id'])]['mean_power_LR']))
    target.append(np.array(row['rise_minus_fall_shape_db_LR']).mean(axis=1))
target=np.array(target);folds=[]
for j,row in enumerate(pairs):
    keep=[i for i in range(len(pairs)) if i!=j];training=[baseline[i] for i in keep];db,fold_scalar=normalize(fit(training,target[keep]),training)
    result=predicted(db,baseline[j]);error=result-target[j]
    folds.append(dict(held_out=row['id'],training=[pairs[i]['id'] for i in keep],normalization_db=fold_scalar,target_db=target[j].tolist(),prediction_db=result.tolist(),
        error_db=error.tolist(),rms_error_db=float(np.sqrt(np.mean(error**2))),flat_rms_error_db=float(np.sqrt(np.mean(target[j]**2)))))
db=fit(baseline,target)
# One scalar fixes equal expected28..6k energy on the pooled falling baseline.
db,scalar=normalize(db,baseline)
profile=args.out/'A_rear_rise.colour'
profile.write_text('VSL_OSC_COLOUR 1 7\n'+''.join(f'{order:.17g} {value:.17g}\n' for order,value in zip(np.r_[CENTERS,128.,320.],np.r_[db,0.,0.])),encoding='ascii',newline='\n')
report=dict(schema='vsl.osc-colour-fit/1',analysis_sha256=sha(args.analysis/'report.json'),bands_at_reference_root_hz=BANDS,
    acoustic_root_support_hz=[45,50],knots_order=np.r_[CENTERS,128.,320.].tolist(),knots_db=np.r_[db,0.,0.].tolist(),high_order_policy='Return to unity at order128; preserve all higher orders',profile_sha256=sha(profile),
    equal_expected_power_band_hz=[28,6000],equal_power_scalar_db=float(scalar),folds=folds,
    source_sha256={p.relative_to(Path(__file__).resolve().parents[1]).as_posix():sha(p) for p in (Path(__file__),Path(__file__).parent/'state_colour_v2/features.py')},scope='Diagnostic rise/fall colour only; no driver mapping or new physical source',
    human_accepted=False)
(args.out/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(folds=[(f['held_out'],round(f['rms_error_db'],3),round(f['flat_rms_error_db'],3)) for f in folds],knots_db=db.tolist())))

"""Measure existing single-driver recipes before adding any modulation."""
import argparse
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load,save,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('workspace','capture','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();repo=Path(__file__).resolve().parents[1]
    for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    import soundfile as sf
    from driver_joint_v1.budget import measure
    from joint_envelopes_v1.features import describe
    a.out.mkdir(parents=True,exist_ok=False)
    r=dict(result='running',sources={},inputs={},cases=[])
    try:
        for name in ['tools/measure_F3_driver_joint_v1.py','tools/driver_joint_v1/budget.py','tools/joint_envelopes_v1/features.py','research/F3_driver_joint_v1_plan.json']:
            dst=a.out/'exact_sources'/name;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,dst);r['sources'][name]=sha(dst)
        config=load(repo/'research/F3_driver_joint_v1_plan.json')
        frozen=a.workspace/'baselines/F3_joint_envelopes_v1'
        plan_path=frozen/'source/research/F3_joint_envelopes_v1_plan.json'
        r['inputs'][str(plan_path)]=sha(plan_path);plan=load(plan_path)
        capture=load(a.capture/'report.json');assert capture['result'] in ['known_one_driver_capture_passed','three_separate_F3_driver_recipes_captured']
        r['inputs'][str(a.capture/'report.json')]=sha(a.capture/'report.json')
        for row in capture['cases']:
            base=a.capture/row['label'];variant=row['outputs'][0];assert variant['tag']=='stereo512'
            for name,h in variant['files'].items():assert sha(base/name)==h
            audio,rate=sf.read(base/'stereo512_out.wav',always_2d=True,dtype='float64')
            stems,rate2=sf.read(base/'stereo512_layers.wav',always_2d=True,dtype='float64')
            assert rate==rate2==48000 and audio.shape==(240000,2) and stems.shape==(240000,12)
            first=config['trace']['warmup_frames'];audio=audio[first:];stems=stems[first:].reshape(-1,6,2)
            raw,raw_rate=sf.read(base/'stereo512_raw.wav',always_2d=True,dtype='float64')
            envelope=np.fromfile(base/'stereo512_envelope.f64',dtype='<f8')[first:]
            raw=raw[first:];assert raw_rate==rate and raw.shape==audio.shape and envelope.shape==(len(audio),)
            raw_layers=np.zeros_like(stems);raw_layers[:,0]=raw
            values=measure(audio,stems,plan['measurement'])
            assert values['maximum_canonical_tap_rounding_difference_FS']<=config['gates']['bus_sum_absolute_FS']
            features=describe(values['P_canonical'],values['window_starts'],plan)
            features_DNA=describe(values['P_dna'],values['window_starts'],plan)
            raw_values=measure(raw,raw_layers,plan['measurement'])
            raw_features=describe(raw_values['P_canonical'],values['window_starts'],plan)
            values.update(features)
            for name,value in features_DNA.items():values['DNA_'+name]=value
            for name,value in raw_features.items():values['RAW_'+name]=value
            values.update(audio=audio,layers=stems,raw=raw,envelope=envelope,P_raw=raw_values['P_canonical'])
            raw_error=float(abs(stems[:,0]-raw*envelope[:,None]).max())
            assert raw_error<=config['gates']['bus_sum_absolute_FS']
            folder=a.out/row['label'];folder.mkdir();np.savez_compressed(folder/'arrays.npz',**values)
            trace=lambda M:M.diagonal(axis1=-2,axis2=-1).real.sum(axis=-1)
            power=trace(values['P_canonical']).mean(axis=0)
            dna=trace(values['P_dna']).mean(axis=0);other=trace(values['P_other']).mean(axis=0)
            cross=trace(values['signed_cross']).mean(axis=0)
            cov=features['affine_residual_covariance'][8:,8:]
            eig=np.linalg.eigvalsh(cov)
            result=dict(label=row['label'],selection=row['selection'],seed=row['seed'],windows=len(values['window_starts']),
                arrays_sha256=sha(folder/'arrays.npz'),mean_DNA_fraction=(dna/power).tolist(),mean_other_fraction=(other/power).tolist(),
                mean_signed_cross_fraction=(cross/power).tolist(),HF_PC1_fraction=float(eig[-1]/eig.sum()),
                HF_std_dB=np.sqrt(np.diag(cov)).reshape(4,2).tolist(),
                canonical_tap_rounding_FS=values['maximum_canonical_tap_rounding_difference_FS'],
                RAW_HF_PC1_fraction=float(np.linalg.eigvalsh(raw_features['affine_residual_covariance'][8:,8:])[-1]/np.trace(raw_features['affine_residual_covariance'][8:,8:])),
                raw_enveloped_DNA_difference_FS=raw_error,envelope_minmax=[float(envelope.min()),float(envelope.max())],
                envelope_log_range_dB=float(20*np.log10(envelope.max()/envelope.min())))
            recipe=next((v for v in config['recipes'] if v['selection']==row['selection']),None)
            if recipe and recipe['source_context'] in ['F3_fifth1','F3_fifth2']:
                source_path=frozen/'evidence/measure1'/recipe['source_context']/'arrays.npz'
                r['inputs'][str(source_path)]=sha(source_path)
                source=np.load(source_path)
                delta=source['affine_residual_covariance']-features['affine_residual_covariance']
                np.savez_compressed(folder/'source_comparison.npz',covariance_difference=delta,
                    covariance_difference_eigenvalues=np.linalg.eigvalsh(delta),
                    mean_source_P=source['P'].mean(axis=0),mean_C_P=values['P_canonical'].mean(axis=0))
                result['source_context']=recipe['source_context']
                result['mean_C_minus_source_dB']=(10*np.log10(power/trace(source['P']).mean(axis=0))).tolist()
                result['HF_covariance_difference_min_eigenvalue']=float(np.linalg.eigvalsh(delta[8:,8:]).min())
                result['comparison_sha256']=sha(folder/'source_comparison.npz')
                result['synchronized_source_reconstruction']=False
            r['cases'].append(result);save(a.out/'report.json',r);print('PASS existing driver joint budget',row['label'],flush=True)
        r.update(result='existing_one_driver_joint_budgets_measured',
                 physical_source_separation=False,additional_modulation_qualified=False,shared_C_changed=False)
    except Exception as exc:r.update(result='failed',error=repr(exc));raise
    finally:save(a.out/'report.json',r)


if __name__=='__main__':main()

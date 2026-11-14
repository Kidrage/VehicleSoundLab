"""Known radial/phase controls, then six statistical models and isolated OSC audio."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
from research_archive_v1 import load,save,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('workspace','out'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--stage',choices=['known','real'],required=True)
    for n in ('known','known-audit'):p.add_argument('--'+n,type=Path)
    p.add_argument('--reuse-numeric',type=Path)
    a=p.parse_args();repo=Path(__file__).resolve().parents[1]
    for n in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[n]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    import soundfile as sf
    from scipy.special import ndtri
    from scipy.stats import qmc
    from radial_copula_v1.profile import compile_rows
    from radial_copula_v1.quantiles import integral,decode
    from radial_copula_v1.latent import independent_draws,endpoints
    from radial_copula_v1.render import render
    from radial_copula_v1.observe import describe,json_summary,lag_covariance
    from local_atlas_v1.inputs import manifest
    a.out.mkdir(parents=True,exist_ok=False)
    report=dict(result='running',stage=a.stage,cases=[],sources={},inputs={},commands=[])
    def consume(path):
        report['inputs'][str(path)]=sha(path);return path
    def command(binary,args):
        argv=list(map(str,[binary]+args))
        done=subprocess.run(argv,cwd=repo,capture_output=True,timeout=180)
        log=a.out/f'command{len(report["commands"]):02d}.log';log.write_bytes(done.stdout+done.stderr)
        report['commands'].append(dict(argv=argv,exit_code=done.returncode,log=log.name,sha256=sha(log)))
        save(a.out/'report.json',report);assert done.returncode==0,log
    try:
        sources=['research/radial_copula_v1_plan.json','tools/run_radial_copula_v1.py',
                 'tools/radial_copula_v1/profile.py','tools/radial_copula_v1/quantiles.py',
                 'tools/radial_copula_v1/latent.py','tools/radial_copula_v1/render.py',
                 'tools/radial_copula_v1/observe.py','tools/local_atlas_v1/inputs.py']
        for n in sources:
            dest=a.out/'exact_sources'/n;dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(repo/n,dest);report['sources'][n]=sha(dest)
        plan=load(repo/'research/radial_copula_v1_plan.json');g=plan['gates'];bands=[[3000,6000],[6000,8000],[8000,10000],[10000,14000]]
        parent=a.workspace/'baselines/coefficient_geometry_v1'
        assert sha(consume(parent/'manifest.json'))==load(repo/'research/coefficient_geometry_v1_summary.json')['manifest_sha256']
        entries={r['path']:r['sha256'] for r in load(parent/'manifest.json')['files']}
        def frozen(name):
            path=consume(parent/name);assert sha(path)==entries[name];return path
        for n in ('C_files_sha256.json','voice_files_sha256.json','F2_files_sha256.json'):
            assert all(sha(repo/name)==h for name,h in load(frozen('evidence/'+n)).items())
        def fit(folder,rows):
            model,training=compile_rows(rows,plan['model']['components_cap'],plan['model']['rho_cap'])
            np.savez_compressed(folder/'profile.npz',**model)
            np.savez_compressed(folder/'training.npz',**training)
            second=integral(model['amplitude'],2);target=model['target_amplitude_second']
            error=abs(second-target)
            assert np.all(error<=g['zero_amplitude_absolute']+g['mean_power_relative']*target)
            variance=np.sum(model['basis']**2,axis=1)+model['residual_std']**2
            assert abs(variance-model['active']).max()<=g['unit_feature_variance_absolute']
            return model,training,dict(profile_sha256=sha(folder/'profile.npz'),training_sha256=sha(folder/'training.npz'),
                components=len(model['rho']),active_features=int(model['active'].sum()),
                maximum_mean_power_relative_error=float(np.divide(error,target,out=np.zeros_like(error),where=target>0).max()),
                maximum_unit_feature_variance_error=float(abs(variance-model['active']).max()))
        if a.stage=='known':
            original=load(frozen('evidence/known1/report.json'))
            binary=a.out/'local_atlas_export.exe';shutil.copy2(frozen('evidence/known1/local_atlas_export.exe'),binary)
            report['binary_sha256']=sha(binary)
            for name in plan['known_cases']:
                source_name=name if name in ('steady','AM_only','PM_only','AM_PM') else 'PM_only' if name=='phase_wrap' else 'AM_only'
                values=np.load(frozen(f'evidence/known1/{source_name}/moments.npz'))['rows'].copy()
                z=values.reshape(64,288,2,2);z=z[...,0]+1j*z[...,1]
                if name=='zero':z[:]=0
                if name=='phase_wrap':
                    sign=np.resize([1,1,-1,-1],64)
                    z=abs(z)*np.exp(1j*(3.1*sign[:,None,None]+np.array([0.,.3])[None,None,:]))
                if name=='opposed_stereo_AM':
                    z[:,:,1]=z[np.arange(64)^1,:,1]
                values=np.stack([z.real,z.imag],axis=-1).reshape(64,-1)
                folder=a.out/name;folder.mkdir()
                model,training,metadata=fit(folder,values)
                normal=ndtri(qmc.Sobol(d=model['basis'].shape[0]+len(model['rho']),scramble=True,seed=1).random_base2(10))
                features=independent_draws(model,normal)
                amplitude,phase=decode(model,features,True)
                if name in ('steady','PM_only','phase_wrap'):
                    expected=np.sqrt(np.mean(abs(z)**2,axis=0))
                    movement=np.ptp(amplitude,axis=0)
                    assert np.all(movement<=g['zero_amplitude_absolute']+g['known_PM_relative_amplitude_motion']*expected)
                if name in ('steady','AM_only','opposed_stereo_AM'):
                    difference=np.angle(np.exp(1j*(phase-phase[:1])))
                    assert abs(difference).max()<=g['known_AM_circular_phase_motion_radians']
                if name=='phase_wrap':assert np.ptp(training['phase_unwrapped'],axis=0).max()<.084
                if name=='opposed_stereo_AM':
                    assert np.corrcoef(amplitude[:,63,0],amplitude[:,63,1])[0,1]<-.999999
                wave=folder/'known.wav'
                audio=render(wave,model,64,plan['known_audio_seconds'],1,True,plan['audio']['block'])
                if name=='zero':assert np.array_equal(sf.read(wave,always_2d=True)[0],np.zeros((48000,2)))
                row=dict(label=name,**metadata,audio=audio,wave_sha256=sha(wave),known_no_AM_PM_cross_talk=True)
                report['cases'].append(row);save(a.out/'report.json',report)
                print('PASS known positive radial/circular OSC',name,flush=True)
            report['result']='known_radial_phase_separation_passed'
        else:
            assert a.known and a.known_audit
            known=load(consume(a.known/'report.json'));audit=load(consume(a.known_audit/'report.json'))
            assert known['result']=='known_radial_phase_separation_passed' and audit['result']=='independent_radial_copula_audit_passed'
            assert audit['producer_report_sha256']==sha(a.known/'report.json')
            prior=load(frozen('evidence/real1/report.json'))
            reuse=None
            if a.reuse_numeric:
                reuse=load(consume(a.reuse_numeric/'report.json'))
                assert reuse['result']=='failed' and 'multiple values' in reuse['error']
                assert len(reuse['cases'])==6 and reuse['distribution_validation']['aggregate_CV_error_reduction']>=g['QMC_aggregate_CV_error_reduction_min']
                for n,h in reuse['sources'].items():
                    assert sha(a.reuse_numeric/'exact_sources'/n)==h
                    if n!='tools/run_radial_copula_v1.py':assert sha(repo/n)==h
                for n,h in reuse['inputs'].items():assert sha(n)==h
                report['numeric_reuse']=dict(report_sha256=sha(a.reuse_numeric/'report.json'),reason='Only duplicate seed keyword in audio metadata fixed; model/QMC inputs and executed module sources exact.')
            all_new=[];all_source=[];all_old=[];peak_mean_error=0.
            for original in prior['cases']:
                label=original['label'];folder=a.out/label;folder.mkdir()
                if reuse:
                    old_row=next(r for r in reuse['cases'] if r['label']==label)
                    for n,h in [('profile.npz',old_row['profile_sha256']),('training.npz',old_row['training_sha256'])]+[(f'QMC_{r["seed"]}.npz',r['arrays_sha256']) for r in old_row['QMC']]:
                        source=consume(a.reuse_numeric/label/n);assert sha(source)==h
                        shutil.copy2(source,folder/n)
                    row=dict(old_row,audio=[]);row.pop('temporal',None)
                    all_source.extend(row['source']['CV'])
                    all_old.extend(original['variants'][0]['moments']['model_interpolation']['power_CV'])
                    all_new.extend(np.mean([r['joint']['CV'] for r in row['QMC']],axis=0))
                    peak_mean_error=max(peak_mean_error,max(r['maximum_mean_power_error_dB'] for r in row['QMC']))
                    report['cases'].append(row);save(a.out/'report.json',report)
                    print('PASS exact reuse of numeric model/QMC',label,flush=True)
                    continue
                data=np.load(frozen(f'evidence/real1/{label}/full/moments.npz'))
                values=data['rows'];root=original['variants'][0]['root_hz']
                model,training,metadata=fit(folder,values)
                z=values.reshape(len(values),288,2,2);z=z[...,0]+1j*z[...,1]
                source=describe(abs(z),np.angle(z),root,bands)
                row=dict(label=label,root_hz=root,**metadata,source=json_summary(source),QMC=[],audio=[],
                         source_lag1_power_covariance=lag_covariance(source['power']).tolist())
                all_source.extend(source['CV']);all_old.extend(original['variants'][0]['moments']['model_interpolation']['power_CV'])
                cv=[]
                for seed in plan['stationary_validation']['seeds']:
                    raw=qmc.Sobol(d=model['basis'].shape[0]+len(model['rho']),scramble=True,seed=seed).random_base2(plan['stationary_validation']['Sobol_power'])
                    feature=independent_draws(model,ndtri(raw))
                    amp,phase=decode(model,feature,True)
                    variable=describe(amp,phase,root,bands)
                    fixed=describe(amp,np.broadcast_to(model['fixed_phase'],amp.shape),root,bands)
                    mean_error=float(abs(10*np.log10(variable['mean']/source['mean'])).max())
                    assert mean_error<=g['QMC_mean_power_max_dB']
                    peak_mean_error=max(peak_mean_error,mean_error)
                    assert np.array_equal(variable['power'],fixed['power'])
                    np.savez_compressed(folder/f'QMC_{seed}.npz',normal=raw,**{'joint_'+k:v for k,v in variable.items()},
                                        **{'fixed_'+k:v for k,v in fixed.items()})
                    row['QMC'].append(dict(seed=seed,arrays_sha256=sha(folder/f'QMC_{seed}.npz'),
                        maximum_mean_power_error_dB=mean_error,joint=json_summary(variable),fixed=json_summary(fixed)))
                    cv.append(variable['CV'])
                all_new.extend(np.mean(cv,axis=0))
                report['cases'].append(row);save(a.out/'report.json',report)
                print('PASS six-source positive radial/circular distributions',label,flush=True)
            baseline_error=float(np.linalg.norm(np.array(all_old)-all_source))
            new_error=float(np.linalg.norm(np.array(all_new)-all_source))
            improvement=1-new_error/baseline_error
            report['distribution_validation']=dict(CV_error_old_L2=baseline_error,CV_error_new_L2=new_error,
                aggregate_CV_error_reduction=improvement,maximum_QMC_mean_error_dB=peak_mean_error,
                source_CV=all_source,old_CV=all_old,new_CV=all_new)
            save(a.out/'report.json',report)
            assert improvement>=g['QMC_aggregate_CV_error_reduction_min']
            binary=a.out/'local_atlas_export.exe';shutil.copy2(consume(a.known/'local_atlas_export.exe'),binary)
            assert sha(binary)==known['binary_sha256']
            bank_plan=load(consume(repo/'research/F3_local_atlas_v1_plan.json'))
            members={label:(archive,attempt) for bank in bank_plan['banks'] for archive,attempt,label in bank['cases']}
            for row in report['cases']:
                if row['label'] not in plan['audio']['anchors']:continue
                folder=a.out/row['label'];model=dict(np.load(folder/'profile.npz'));root=row['root_hz']
                archive,attempt=members[row['label']]
                old=a.workspace/'baselines'/archive
                original_path=f'evidence/{attempt}/{row["label"]}/voice.model'
                expected={r['path']:r['sha256'] for r in load(consume(old/'manifest.json'))['files']}[original_path]
                source=consume(old/original_path);assert sha(source)==expected
                shutil.copy2(source,folder/'original.model')
                manifest(folder/'original.manifest',[folder/'original.model'])
                frames=plan['audio']['seconds']*48000
                (folder/'original.trace').write_text(f'VSL_LOCAL_ATLAS_TRACE 1 {frames} 1\n0 {root:.17g} 1 1\n',encoding='ascii')
                for seed in plan['audio']['seeds']:
                    prefix=folder/f'original_{seed}'
                    command(binary,[folder/'original.manifest',folder/'original.trace',prefix,seed,512])
                    row['audio'].append(dict(variant='original',seed=seed,file=prefix.with_suffix('.wav').name,
                        sha256=sha(prefix.with_suffix('.wav'))))
                    for variant in plan['audio']['variants']:
                        path=folder/f'{variant}_{seed}.wav'
                        info=render(path,model,root,plan['audio']['seconds'],seed,variant=='joint_phase',plan['audio']['block'])
                        row['audio'].append(dict(variant=variant,file=path.name,sha256=sha(path),**info))
                    state,_=endpoints(model,int(np.floor((frames-1)*root/12000))+2,seed)
                    feature=independent_draws(model,state)
                    amp,phase=decode(model,feature,True)
                    d=describe(amp,phase,root,bands)
                    np.savez_compressed(folder/f'temporal_{seed}.npz',**d,lag1_covariance=lag_covariance(d['power']))
                    row.setdefault('temporal',[]).append(dict(seed=seed,sha256=sha(folder/f'temporal_{seed}.npz'),
                        lag1_covariance=lag_covariance(d['power']).tolist(),**json_summary(d)))
                    save(a.out/'report.json',report)
                    print('PASS isolated statistical OSC audio',row['label'],seed,flush=True)
                if row['label']==plan['audio']['anchors'][0]:
                    path=folder/'joint_phase_block37.wav'
                    render(path,model,root,plan['audio']['seconds'],plan['audio']['seeds'][0],True,plan['audio']['block_identity_second'])
                    first=sf.read(folder/f'joint_phase_{plan["audio"]["seeds"][0]}.wav',always_2d=True)[0]
                    second=sf.read(path,always_2d=True)[0]
                    error=float(abs(first-second).max())
                    assert error<=g['block_wave_absolute_FS'];row['block37_1024_maximum_PCM_error_FS']=error
            report.update(result='six_radial_copula_models_and_two_anchor_audio_ready',new_audio_candidate=True,
                          source_only_not_driving_replay=True,physical_phase_identified=False,heard=False,runtime_changed=False)
    except Exception as exc:
        report.update(result='failed',error=repr(exc));raise
    finally:save(a.out/'report.json',report)


if __name__=='__main__':main()

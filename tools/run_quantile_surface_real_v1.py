"""All6x3x3 new row-quantile waves with original observer and signed budget."""
import argparse,os,shutil,sys
from pathlib import Path
from research_archive_v1 import load,save,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('workspace','seam','seam-audit','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from quantile_surface_v1.render import generate
    from quantile_surface_v1.moments import conditional_mixture,quantile_blend
    from quantile_surface_v1.prepare import canonical_rows
    from phase_input_paths_v1.replay import fields
    from conditional_phase_time_v1.observer import analyze,summary,power_statistics
    from carrier_transfer_v1.spectral import measure,collapse,summary as group_summary
    repo=Path(__file__).resolve().parents[1];a.out.mkdir(parents=True,exist_ok=False)
    r=dict(result='running',pid=os.getpid(),cases=[],sources={},inputs={})
    print('QUANTILE_SURFACE_PRODUCER_PID',os.getpid(),flush=True)
    try:
        seam=load(a.seam/'report.json');audit=load(a.seam_audit/'report.json')
        assert seam['result']=='quantile_seam_known_ready' and audit['result']=='independent_quantile_seam_known_passed'
        assert audit['endcap_preparation_verified']
        assert audit['producer_sha256']==sha(a.seam/'report.json') and audit['auditor_sha256']==sha(repo/'tools/audit_quantile_surface_seam_v1.py')
        for name,digest in seam['sources'].items():assert sha(repo/name)==sha(a.seam/'exact_sources'/name)==digest
        r.update(seam_sha256=sha(a.seam/'report.json'),seam_audit_sha256=sha(a.seam_audit/'report.json'))
        names=('research/quantile_surface_real_v1_plan.json','tools/run_quantile_surface_real_v1.py',
               'tools/quantile_surface_v1/render.py','tools/quantile_surface_v1/surface.py','tools/quantile_surface_v1/moments.py','tools/quantile_surface_v1/prepare.py',
               'tools/phase_input_paths_v1/replay.py','tools/phase_input_paths_v1/factor.py','tools/conditional_phase_time_v1/mapping.py',
               'tools/radial_copula_v1/latent.py','tools/radial_copula_v1/quantiles.py','tools/conditional_phase_time_v1/observer.py',
               'tools/sound_dna/windowed.py','tools/carrier_transfer_v1/groups.py','tools/carrier_transfer_v1/spectral.py')
        for name in names:
            dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,dest);r['sources'][name]=sha(dest)
        plan=load(repo/names[0]);gate=plan['gates']
        parent=a.workspace/'baselines/conditional_phase_time_v1';stream=a.workspace/'baselines/phase_stream_control_v1';inputs=a.workspace/'baselines/phase_input_paths_v1'
        for root,key in ((parent,'conditional_phase_time_v1'),(stream,'phase_stream_control_v1'),(inputs,'phase_input_paths_v1')):
            assert sha(root/'manifest.json')==load(repo/f'research/{key}_summary.json')['manifest_sha256']
        entries={x['path']:x['sha256'] for x in load(parent/'manifest.json')['files']}
        def frozen(name):
            path=parent/name;assert sha(path)==entries[name];r['inputs'][str(path)]=entries[name];return path
        old=load(frozen('evidence/real1/report.json'));save(a.out/'report.json',r)
        for oldrow in old['cases']:
            label,root=oldrow['label'],oldrow['root_hz'];folder=a.out/label;folder.mkdir()
            with np.load(frozen(f'evidence/real1/{label}/bundle.npz')) as z:bundle={k:z[k] for k in z.files}
            # Match the old decoder's forced 0/1 endcaps, not LP row-sum drift.
            endcaps={}
            for name in plan['decoders']:
                original=bundle[name];prepared=canonical_rows(original)
                endcaps[name]=float(abs(prepared-original).max());bundle[name]=prepared
            frozen(f'evidence/real1/{label}/source.npz')
            h=len(bundle['mean_product']);moments={};moment_desc={}
            for name in plan['decoders']:
                original=np.empty((h,bundle['knots'].shape[1]-1),complex);candidate=np.empty_like(original)
                for j in range(h):
                    c=bundle[name][j];lo=bundle['low'][j];hi=bundle['high'][j]
                    assert np.all(np.diff(c,axis=1)>0) and np.allclose(lo[1:],hi[:-1],rtol=0,atol=0)
                    for i in range(len(c)-1):
                        original[j,i]=conditional_mixture(.5,c[i],c[i+1],lo,hi)
                        candidate[j,i]=quantile_blend(.5,c[i],c[i+1],lo,hi)
                        for weight in (0.,1.):assert abs(quantile_blend(weight,c[i],c[i+1],lo,hi)-conditional_mixture(weight,c[i],c[i+1],lo,hi))<gate['circular_moment']
                moments[name+'_old']=original;moments[name+'_new']=candidate
                moment_desc[name]=dict(count=original.size,mean_loss=float(abs(candidate-original).mean()),maximum_loss=float(abs(candidate-original).max()))
            moment_path=folder/'midpoint_moments.npz';np.savez_compressed(moment_path,**moments)
            row=dict(label=label,root_hz=root,source_rows=oldrow['source_rows'],seeds=[],endcap_maximum_change=endcaps,midpoint_moments=dict(file=moment_path.name,sha256=sha(moment_path),summary=moment_desc))
            for seed in oldrow['seeds']:
                with np.load(frozen(f'evidence/real1/{label}/probe_{seed["seed"]}.npz')) as z:capture={k:z[k] for k in ('state','independent_state','probe_positions','probe_amplitude','probe_common')}
                amplitude,common,uniform=fields(bundle,capture,plan['frames'],plan['block'])
                assert abs(amplitude[capture['probe_positions']]-capture['probe_amplitude']).max()<2e-12
                assert abs(common[capture['probe_positions']]-capture['probe_common']).max()<2e-12
                other=None
                if not r['cases'] and seed['seed']==plan['seeds'][0]:other=fields(bundle,capture,plan['frames'],plan['identity_block'])
                sr=dict(seed=seed['seed'],decoders={})
                for name in plan['decoders']:
                    group,diagnostics=generate(bundle,amplitude,common,uniform,root,plan['carrier_edges_Hz'],plan['bands_Hz'],name)
                    identity=None
                    if other is not None:
                        paired,_=generate(bundle,*other,root,plan['carrier_edges_Hz'],plan['bands_Hz'],name)
                        identity=float(abs(paired-group).max());assert identity<gate['wave_identity_FS'];del paired
                    wave=group.sum(axis=1);observed=analyze(wave,h,root,plan['bands_Hz']);spectral=measure(group,root,plan['bands_Hz'])
                    values=dict(grouped_audio=group,audio=wave,**diagnostics,**observed)
                    for prefix in ('line','broad'):
                        values.update({prefix+'_'+k:v for k,v in group_summary(spectral[prefix+'_Gram']).items()})
                        power=observed['power' if prefix=='line' else 'broadband_power'];cross=observed['cross' if prefix=='line' else 'broadband_cross']
                        collapsed=collapse(spectral[prefix+'_Gram']);scale=np.maximum(power.reshape(241,4,2).mean(axis=(0,2)),1e-24)
                        assert (abs(collapsed[:,:,[0,1],[0,1]].real.reshape(241,8)-power).reshape(241,4,2)/scale[None,:,None]).max()<gate['Gram_per_band_scaled']
                        width=oldrow['source_rows'];chunks=[power_statistics(power[t:t+width],cross[t:t+width]) for t in range(0,len(power)-width+1,width)]
                        for field in ('mean','CV','complex_coherence'):values['chunks_'+prefix+'_'+field]=np.stack([c[field] for c in chunks])
                    values.update(spectral)
                    path=folder/f'{name}_{seed["seed"]}.npz';np.savez_compressed(path,**values)
                    sr['decoders'][name]=dict(file=path.name,sha256=sha(path),chunk_identity_FS=identity,statistics=summary(observed))
                    print('GENERATED Q surface',label,seed['seed'],name,flush=True)
                row['seeds'].append(sr);del amplitude,common,uniform,other
            r['cases'].append(row);save(a.out/'report.json',r)
        assert len(r['cases'])==6
        r.update(result='quantile_surface_all54_ready',new_waves=54,frames=plan['frames'],new_random_draws=False,native_or_C_or_hearing=False)
        save(a.out/'report.json',r);print(r['result'],flush=True)
    except BaseException as e:r.update(result='failed',error=repr(e));save(a.out/'report.json',r);raise


if __name__=='__main__':main()

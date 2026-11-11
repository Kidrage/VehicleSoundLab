"""Re-estimate actual C coefficients; audit provenance and freeze local study."""
import json
import shutil
from runtime_review import ROOT,sha
from reference_segments import checked_source,CATALOG
import numpy as np
import soundfile as sf

OUT=ROOT/'renders/observed_dna_v1'
SNAP=ROOT/'baselines/observed_dna_v1'
STUDY=ROOT/'references/analysis/phase_fingerprint_v1'


def read(path):return json.loads(path.read_text(encoding='utf-8'))


def dna(path):
    words=path.read_text().split();assert words[:2]==['VSL_DNA','1']
    root=float(words[2]);n=int(words[3]);values=np.asarray(words[4:],float).reshape(n,2)
    return root,values[:,0]*np.exp(1j*values[:,1])


def recovered_coefficients(path,root,count):
    x,sr=sf.read(path,always_2d=True);assert sr==48000 and sf.info(path).subtype=='FLOAT'
    # Independent inverse problem on 5120 samples of the actual native output.
    # It does not use the renderer's time-series oracle or native recurrence.
    t=np.arange(5120)/sr;angle=2*np.pi*root*t[:,None]*np.arange(1,count+1)[None,:]
    design=np.column_stack([np.ones(len(t)),np.cos(angle),np.sin(angle)])
    coefficients,_,rank,_=np.linalg.lstsq(design,x[:len(t)],rcond=None)
    assert rank==2*count+1 and abs(coefficients[0]).max()<1e-8
    return coefficients[1:count+1]-1j*coefficients[count+1:],x


def independent_sparse_checks(base,supplement):
    checks={}
    for key,row in base['runs'].items():
        assert row['phase_transfer']['channels'][0]['status']=='unmeasured'
        a=np.array(row['past']['real'])+1j*np.array(row['past']['imag'])
        b=np.array(row['future']['real'])+1j*np.array(row['future']['imag'])
        n=min(len(a),len(b));a=a[:n];b=b[:n];observed=supplement['runs'][key]
        checks[key]=[]
        for c in range(2):
            indices=[]
            for d in range(1,17):
                for center in range(d,n-d):
                    ix=np.array([center-d,center,center+d])
                    if min(abs(a[ix,c]))>=.03*max(abs(a[:,c])) and min(abs(b[ix,c]))>=.03*max(abs(b[:,c])):
                        indices.append(ix)
            actual=observed['combined_channels'][c];assert actual['triplets']==len(indices)
            if len(indices)<3:
                assert actual['status']=='unmeasured';checks[key].append(dict(status='unmeasured',triplets=len(indices)));continue
            ix=np.asarray(indices);assert np.array_equal(ix+1,actual['triplet_indices'])
            past_phase=np.angle(a[ix[:,0],c])-2*np.angle(a[ix[:,1],c])+np.angle(a[ix[:,2],c])
            future_phase=np.angle(b[ix[:,0],c])-2*np.angle(b[ix[:,1],c])+np.angle(b[ix[:,2],c])
            weight=np.min(abs(b[ix,c]),axis=1)**2
            error=float(np.average(2-2*np.cos(future_phase-past_phase),weights=weight))
            flat=float(np.average(2-2*np.cos(future_phase),weights=weight))
            assert abs(error-actual['future_weighted_phase_chord_error'])<1e-12
            assert abs(flat-actual['zero_curvature_chord_error'])<1e-12
            checks[key].append(dict(status='measured',triplets=len(ix),independent_chord_error=error,independent_zero_curvature_error=flat))
    return checks


def main():
    if (OUT/'verification.json').exists() or SNAP.exists():raise SystemExit('Preserve frozen observed_dna_v1.')
    result=read(OUT/'results.json');base=read(STUDY/'results.json')
    sparse_path=ROOT/'references/analysis/phase_spaced_triplets_v1/results.json';sparse=read(sparse_path)
    for group in ['files','inputs','sources','binaries']:
        for name,digest in result[group].items():assert sha((OUT if group=='files' else ROOT)/name)==digest,(group,name)
    assert sha(ROOT/result['page']['file'])==result['page']['sha256']
    for record,folder in [(base,STUDY),(sparse,sparse_path.parent)]:
        for group in ['inputs','sources']:
            for name,digest in record[group].items():assert sha(ROOT/name)==digest,name
        for name,digest in record.get('files',{}).items():assert sha(folder/name)==digest,name
    assert sha(CATALOG)==base['reference']['catalog_sha256']
    browser=read(OUT/'browser_qa.json');assert browser['result']=='pass' and browser['audio_metadata_loads']==6
    for key in ['actual_muted_playback','position_and_playing_state_preserved','case_change_stops_at_zero',
        'reference_exclusive_playback','http_and_file_entry','figure_loaded']:assert browser[key],key
    assert not browser['mobile_horizontal_overflow'] and not browser['javascript_errors']
    pipeline=read(OUT/'interchange/dna_pipeline_check.json');assert pipeline['result']=='pass' and pipeline['dsp_version']=='0.16.0'
    assert sha(ROOT/'build-v016/Release/vsl_render.exe')==pipeline['renderer_sha256']
    recovered={};phase_checks={}
    for name,snapshot in base['snapshots'].items():
        recovered[name]={};zs={}
        for method in ['fitted','common_flat']:
            paths=[STUDY/snapshot['files'][method][c]['file'] for c in ['L','R']]
            roots,coefficients=zip(*(dna(p) for p in paths));assert roots[0]==roots[1]
            z=np.column_stack(coefficients);zs[method]=z
            entry=result['cases'][name]['variants'][method]
            fitted,x=recovered_coefficients(OUT/entry['raw'],roots[0],len(z))
            error=float(abs(fitted-z).max());assert error<2e-8
            assert sha(OUT/entry['raw'])==sha(OUT/f'{name}_{method}_block1.wav')
            y,sr=sf.read(OUT/entry['audition'],always_2d=True);assert sr==48000 and sf.info(OUT/entry['audition']).subtype=='PCM_24'
            assert abs(y).max()<=.85 and entry['gain_db']==20*np.log10(.5)
            fade=np.ones(len(x));fade[:240]=np.arange(240)/239;fade[-240:]=np.arange(239,-1,-1)/239
            q=float(abs(y-x*.5*fade[:,None]).max());assert q<=2**-23+1e-12
            recovered[name][method]=dict(maximum_complex_coefficient_error=error,
                complete_raw_wav_block1_vs257_identical=True,independent_audition_quantization_error=q)
        a=zs['fitted'];b=zs['common_flat']
        magnitude=float(abs(abs(a)-abs(b)).max())
        cross=float(abs(a[:,0]*a[:,1].conj()-b[:,0]*b[:,1].conj()).max())
        assert magnitude<1e-14 and cross<1e-14
        phase_checks[name]=dict(maximum_harmonic_magnitude_difference=magnitude,
            maximum_complex_LR_cross_coefficient_difference=cross)
    sparse_checks=independent_sparse_checks(base,sparse)
    native=read(ROOT/'renders/v0.16.0/verification.json');preserved={}
    for name,digest in native['binaries'].items():assert sha(ROOT/'build-v016/Release'/name)==digest,name
    for item in read(ROOT/'baselines/v0.16.0/manifest.json')['files']:
        name=item['path']
        if name.startswith(('src/','tests/')) or name in ['CMakeLists.txt','Launch.cmd','Launch-character.cmd','build.ps1','AGENTS.md']:
            assert sha(ROOT/name)==item['sha256'],name;preserved[name]=item['sha256']
    assert len(preserved)==144
    for name in ['src/core/dna.c','src/core/high_orders.c','src/core/exhaust_spectrum.c','src/profiles/high_orders.c']:
        assert sha(ROOT/name)==sha(ROOT/'baselines/v0.11.0'/name),name
    media={name:checked_source(name) for name in ['A','B']}
    history={p.parent.name:sha(p) for p in sorted((ROOT/'baselines').glob('*/manifest.json'))};assert len(history)==27
    paths=set(result['sources'])|set(result['binaries'])|set(result['inputs'])|{
        'tools/verify_observed_dna.py','tools/verify_observed_dna_ui.cjs','tools/runtime_review.py','tools/reference_segments.py',
        'tools/ridge_tracks.py','tools/check_dna_pipeline.py','tools/analyze_audio.py','references/segments_v1.json',
        'research/录音DNA相位实验V1.md','research/录音DNA相位试听V1.html','research/goal_progress_observed_dna_v1.json','README.md'}
    paths.update(p.relative_to(ROOT).as_posix() for p in STUDY.rglob('*') if p.is_file())
    paths.update(p.relative_to(ROOT).as_posix() for p in sparse_path.parent.rglob('*') if p.is_file())
    verification=dict(result='pass',study='observed_dna_v1',runtime='0.16.0 unchanged',
        independently_recovered_C_coefficients=recovered,phase_only_variant_checks=phase_checks,
        independently_recomputed_sparse_checks=sparse_checks,DNA_interchange=pipeline,
        native_source_and_contract_files_unchanged=preserved,native_binaries_unchanged=native['binaries'],
        approved_media=media,catalog_sha256=sha(CATALOG),previous_snapshot_manifest_identities=history,
        source_and_build_files={name:sha(ROOT/name) for name in sorted(paths)},
        artifacts={p.relative_to(OUT).as_posix():sha(p) for p in sorted(OUT.rglob('*')) if p.is_file()},
        scope='Local mixed-observation DNA and descriptive phase checks; no native version/voice change, inferred physical engine banks, measured RPM, full driving reconstruction, subjective acceptance or array listening.')
    (OUT/'verification.json').write_text(json.dumps(verification,indent=2,allow_nan=False),encoding='utf-8')
    SNAP.mkdir()
    for name in sorted(paths):
        target=SNAP/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,target)
    for p in sorted(OUT.rglob('*')):
        if p.is_file():
            target=SNAP/p.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target)
    files=[dict(path=p.relative_to(SNAP).as_posix(),sha256=sha(p)) for p in sorted(SNAP.rglob('*')) if p.is_file()]
    manifest=dict(study='observed_dna_v1',base_runtime='0.16.0 unchanged',files=files,
        native_source_manifest_sha256=sha(ROOT/'baselines/v0.16.0/manifest.json'),
        storage='All study C/analysis/player sources,12 local DNA files, analysis/render evidence, float and PCM auditions, manual approved reference derivative and initial label correction retained. Original raw media/float masters are hash-bound at their existing paths. Native include source dependency stays in baselines/v0.16.0.',
        status='Frozen optional static observation-DNA diagnosis; cross-window phase mapping and subjective improvement not established.')
    (SNAP/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    assert all(sha(SNAP/item['path'])==item['sha256'] for item in files)
    complete=dict(result='pass',snapshot_files=len(files),manifest_sha256=sha(SNAP/'manifest.json'),
        verification_sha256=sha(OUT/'verification.json'),native_files_unchanged=len(preserved),previous_manifests=len(history),
        maximum_recovered_complex_coefficient_error=max(v['maximum_complex_coefficient_error'] for c in recovered.values() for v in c.values()))
    (OUT/'freeze_complete.json').write_text(json.dumps(complete,indent=2),encoding='utf-8');print(json.dumps(complete,indent=2))


if __name__=='__main__':main()

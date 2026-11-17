"""Freeze executed code/binaries and verify both strict replay identities."""
import hashlib,json,shutil
from pathlib import Path
from copy import deepcopy
import numpy as np
import soundfile as sf
from vehicle_controller.native import Bridge,Engine
from vehicle_controller import take

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def main():
    repo=Path(__file__).resolve().parents[1];root=Path('E:/VehicleSoundLab/references/analysis');output=root/'source_perf_v1/delivery1';output.mkdir(exist_ok=False)
    new=Bridge(repo);old=Bridge(repo,root/'source_perf_v1/before/vsl_source_bridge.dll')
    results={};waveforms={}
    for name,b in (('before',old),('after',new)):
        control=b.initial(0)[0];control.update(ignition=1,start_id=1)
        value=take.create(b,0,control);pcm=[]
        with Engine(b,0) as e:
            e.set(control)
            for n in range(20):
                if n==7:control['throttle']=.7;e.set(control);take.append(value,e.frame,e.controls)
                pcm.append(e.process(480))
            value['frames']=e.frame
        path=output/(name+'.vsltake.json');take.save(path,value);loaded=take.read(path,b)
        other=new if name=='before' else old
        try:take.read(path,other)
        except ValueError as error:
            assert '另一版 C 引擎' in str(error);mismatch=True
        else:raise AssertionError('Wrong engine identity was accepted')
        rendered=[];index=0
        with Engine(b,0) as e:
            e.set(loaded['initial'])
            while e.frame<loaded['frames']:
                data,index=take.replay_block(e,loaded,index,217);rendered.append(data)
        assert b''.join(pcm)==b''.join(rendered)
        waveforms[name]=np.frombuffer(b''.join(pcm),dtype='<f4')
        results[name]=dict(bridge_sha256=b.sha256,arbitrary_partition_replay_exact=True,other_engine_refused=mismatch,frames=value['frames'])
    paired=json.loads((root/'source_perf_v1/paired2/report.json').read_text());assert new.sha256==paired['new_sha256'] and old.sha256==paired['old_sha256']
    # Check candidate only refines numerical evaluation after its first freeze.
    a,_=sf.read(root/'startup_rotation_v1/listen1/Candidate.wav',dtype='float32');b,_=sf.read(root/'startup_rotation_v1/listen2/Candidate.wav',dtype='float32')
    delta=float(np.max(abs(a-b)));assert delta<2e-6
    results.update(shared_kernel_mixed_stem_max=max(row['stems']['max_error'] for row in paired['cases'].values()),
        crank_cache_change_max=delta,final_review=str(root/'startup_rotation_v1/listen2'),performance_claim='PC paired C-boundary timing, not target MCPS',human_crank_accepted=False)
    # Snapshot all source units participating in this work, not build caches or
    # original media. Runtime model bytes are already self-contained in review.
    touched=['modules/partitioned_fir','modules/modal_source','modules/resonant_detail','modules/drive_recipe','modules/stereo_resonance','modules/crank_rotation','modules/startup_character','experiments/startup_character_v1','tools/startup_rotation_v1','tools/startup_character_v1','tools/vehicle_controller']
    paths=[]
    for folder in touched:
        paths.extend(p for p in (repo/folder).rglob('*') if p.is_file() and p.suffix in ('.c','.h','.py','.txt','.md'))
    singles=['tools/compare_source_perf_v1.py','tools/upgrade_startup_rotation_v1.py','tools/audit_startup_rotation_v1.py','tools/finalize_source_perf_rotation_v1.py','tools/render_startup_expression_v1.py','tools/run_vehicle_controller.py','tools/verify_vehicle_controller_v1.py','tools/verify_vehicle_host_replay_v1.py','Build-Vehicle-Source.ps1','Launch-Vehicle-Sound-v13.cmd','AGENTS.md','handoff/性能优化与拖转升级计划V1.md','handoff/性能优化与持续拖转升级结果V1.md','handoff/统一系统报告.md']
    paths.extend(repo/p for p in singles)
    manifest=[]
    for source in sorted(set(paths)):
        relative=source.relative_to(repo);dest=output/'exact_sources'/relative;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,dest)
        manifest.append(dict(path=str(relative).replace('\\','/'),sha256=sha(dest),bytes=dest.stat().st_size))
    shutil.copy2(new.path,output/'vsl_source_bridge.dll')
    for candidate in ('listen1','listen2'):
        folder=root/'startup_rotation_v1'/candidate
        if candidate=='listen2':
            # Bind the exact final sources to the final listening artifacts.
            save(folder/'source-manifest.json',manifest)
            save(folder/'final-bindings.json',dict(main_sha256=new.sha256,event_sha256=sha(folder/'startup_character_bridge.dll'),audio_sha256=sha(folder/'Candidate.wav'),exact_sources=str(output/'exact_sources')))
    save(output/'verification.json',results);save(output/'source-manifest.json',manifest)
    # Recursive artifact manifest is outside its own hash scope.
    artifacts=[]
    for base in (output,root/'startup_rotation_v1/listen2'):
        for path in sorted(base.rglob('*')):
            if path.is_file():artifacts.append(dict(path=str(path),sha256=sha(path),bytes=path.stat().st_size))
    save(output/'artifacts.json',artifacts)
    print(json.dumps(results,ensure_ascii=False),flush=True)
if __name__=='__main__':main()

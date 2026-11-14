"""Known catalog fixtures first, then three separate one-driver F3 recipes."""
import argparse
from pathlib import Path
import shutil
import subprocess
from research_archive_v1 import load,save,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('workspace','build','out'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--stage',choices=['known','real'],required=True);p.add_argument('--known',type=Path)
    p.add_argument('--previous',type=Path)
    a=p.parse_args();repo=Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True,exist_ok=False)
    empty=a.out/'no_external_voices';empty.mkdir()
    binary=a.build/'joint_capture.exe';assert load(a.build/'report.json')['result']=='joint_capture_built'
    assert sha(binary)==load(a.build/'report.json')['binary_sha256']
    r=dict(result='running',stage=a.stage,commands=[],cases=[],sources={},inputs={})
    plan=load(repo/'research/F3_driver_joint_v1_plan.json')
    def run(argv,expected=0,cwd=None):
        argv=list(map(str,[binary]+argv));done=subprocess.run(argv,cwd=cwd or repo,capture_output=True,timeout=180)
        log=a.out/f'command{len(r["commands"]):03d}.log';log.write_bytes(done.stdout+done.stderr)
        r['commands'].append(dict(argv=argv,cwd=str(cwd or repo),exit_code=done.returncode,log=log.name,sha256=sha(log)))
        save(a.out/'report.json',r);assert done.returncode==expected,log
        return done
    try:
        for name in ['tools/run_F3_driver_joint_v1.py','research/F3_driver_joint_v1_plan.json']:
            dst=a.out/'exact_sources'/name;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,dst);r['sources'][name]=sha(dst)
        prior=a.workspace/'baselines/catalog_local_F3_v1/evidence'
        r['protected_before']=dict(load(prior/'C_files_sha256.json'),**load(prior/'voice_files_sha256.json'))
        assert all(sha(repo/n)==h for n,h in r['protected_before'].items())
        assert run(['--describe']).stdout.strip()==b'vsl.joint-capture/2'
        if a.stage=='real':
            assert a.known and load(a.known/'report.json')['result']=='known_one_driver_capture_passed'
            r['inputs'][str(a.known/'report.json')]=sha(a.known/'report.json')
            selections=[v['selection'] for v in plan['recipes']];seeds=plan['seeds']
        else:
            selections=plan['known_before_real']['catalog_selections'];seeds=plan['known_before_real']['seeds']
        for selection in selections:
            for seed in seeds:
                label=f'voice{selection}_seed{seed}';folder=a.out/label;folder.mkdir()
                take=folder/'drive.vslrun';run(['make',selection,seed,take])
                r['inputs'][str(take)]=sha(take)
                outputs=[]
                variants=[('stereo512',512,2)]
                if a.stage=='known' or seed==seeds[0]:variants += [('stereo37',37,2),('wide257',257,12)]
                for tag,block,channels in variants:
                    prefix=folder/tag;run(['export',take,prefix,block,channels],cwd=empty)
                    info=load(prefix.with_suffix('.json'))
                    assert info['verified'] and info['frames']==240000
                    assert info['max_dry_bus_sum_error_FS']<=plan['gates']['bus_sum_absolute_FS']
                    outputs.append(dict(tag=tag,channels=channels,block=block,report=info,
                        files={prefix.name+s:sha(Path(str(prefix)+s)) for s in ['_out.wav','_layers.wav','_raw.wav','_envelope.f64','.csv','.json']}))
                ids={v['report']['render_id'] for v in outputs};assert len(ids)==1
                assert len({v['report']['source_hash'] for v in outputs})==1
                for value in outputs[1:]:
                    tag=value['tag']
                    assert sha(folder/(tag+'_layers.wav'))==sha(folder/'stereo512_layers.wav')
                    assert sha(folder/(tag+'.csv'))==sha(folder/'stereo512.csv')
                    assert sha(folder/(tag+'_raw.wav'))==sha(folder/'stereo512_raw.wav')
                    assert sha(folder/(tag+'_envelope.f64'))==sha(folder/'stereo512_envelope.f64')
                    if value['channels']==2:assert sha(folder/(tag+'_out.wav'))==sha(folder/'stereo512_out.wav')
                if a.stage=='known':
                    before=sha(take);run(['make',selection,seed,take],3);assert sha(take)==before
                    before=sha(folder/'stereo512_out.wav');run(['export',take,folder/'stereo512',512,2],4,cwd=empty)
                    assert sha(folder/'stereo512_out.wav')==before
                r['cases'].append(dict(label=label,selection=selection,seed=seed,take_sha256=sha(take),outputs=outputs,
                    canonical_hash_verified=True,external_voices_absent_for_export=True,block_and_layout_checks=len(outputs)>1))
                if a.previous:
                    previous=a.previous/label
                    assert sha(take)==sha(previous/'drive.vslrun')
                    for output in outputs:
                        for suffix in ['_out.wav','_layers.wav','.csv']:
                            name=output['tag']+suffix;assert sha(folder/name)==sha(previous/name)
                save(a.out/'report.json',r);print('PASS one-driver capture',label,flush=True)
        if a.stage=='known':
            for args in [['make','5','0'],['make','-1','1'],['make','4294967296','1'],['make','5','18446744073709551616']]:
                path=a.out/('invalid_'+str(len(r['commands']))+'.vslrun');run(args+[path],2);assert not path.exists()
            parent=a.workspace/'baselines/catalog_local_F3_v1'
            historical=parent/'evidence/regress1/new_render/voice_5.vslrun'
            manifest={v['path']:v['sha256'] for v in load(parent/'manifest.json')['files']}
            assert sha(historical)==manifest[historical.relative_to(parent).as_posix()]
            r['inputs'][str(historical)]=sha(historical)
            run(['export',historical,a.out/'historical5',257,2],cwd=empty)
            expected=historical.with_suffix('.wav');assert sha(expected)==manifest[expected.relative_to(parent).as_posix()]
            assert sha(a.out/'historical5_out.wav')==sha(expected)
            r['historical_owned_take_and_WAV_exact']=True
        assert all(sha(repo/n)==h for n,h in r['protected_before'].items())
        r.update(result='known_one_driver_capture_passed' if a.stage=='known' else 'three_separate_F3_driver_recipes_captured',
            binary_sha256=sha(binary),previous_capture_exact=bool(a.previous),sample_loop=False,shared_C_changed=False,heard=False,physical_RPM_load_or_7_1_4=False)
    except Exception as exc:r.update(result='failed',error=repr(exc));raise
    finally:save(a.out/'report.json',r)


if __name__=='__main__':main()

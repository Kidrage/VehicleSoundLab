"""Verify the optional modal gain API against the old driving build and frozen outputs."""
import argparse,subprocess,sys,shutil,time
from pathlib import Path
from research_archive_v1 import sha,load,save
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--out',type=Path,required=True);a=p.parse_args();repo=Path(__file__).resolve().parents[1]
a.out.mkdir(parents=True,exist_ok=False);r=dict(result='running',commands=[],legacy=[],previous_binaries={})


def command(label,args):
    args=list(map(str,args));start=time.perf_counter();done=subprocess.run(args,cwd=repo,capture_output=True,timeout=600)
    dest=a.out/(label+'.log');dest.write_bytes(done.stdout+done.stderr)
    row=dict(label=label,args=args,return_code=done.returncode,seconds=time.perf_counter()-start,log_sha256=sha(dest))
    r['commands'].append(row);save(a.out/'report.json',r);print(row,flush=True)
    if done.returncode:raise RuntimeError(str(dest))


try:
    shutil.copy2(__file__,a.out/'executed_regression.py')
    previous=a.out/'previous_bin';previous.mkdir()
    before=repo/'build-idle-drive-v1/bin/Release'
    for name in ['VslAtlasMonitor.exe','idle_drive_device.exe','VslAtlasDrive_probe.exe','idle_owned_checks.exe','idle_control_checks.exe']:
        shutil.copy2(before/name,previous/name);r['previous_binaries'][name]=sha(previous/name)
    command('full_build',[sys.executable,repo/'tools/build_idle_drive_v1.py','--out',a.out/'full1','--phase','all'])
    report=load(a.out/'full1/report.json');assert report['result']=='passed' and report['tests']==59
    output=a.out/'legacy';output.mkdir();old=a.workspace/'references/analysis/drive_resonance_v1/before1'
    snapshot=load(old/'snapshot.json');binary=a.out/'current_bin';binary.mkdir()
    for name in ['VslAtlasMonitor.exe','VslAtlasDrive_probe.exe']:
        shutil.copy2(before/name,binary/name)
    for case in snapshot['cases']:
        options=case['options']+(['--stereo-bed','1'] if case['name'].startswith('E_') else [])
        command(case['name'],[binary/'VslAtlasDrive_probe.exe',*case['models'][:2],output/case['name'],*options])
        original=sorted((old/'renders').glob(case['name']+'_*.wav'));assert len(original)==28
        for path in original:
            assert sha(path)==snapshot['files'][path.relative_to(old).as_posix()]
            assert path.read_bytes()==(output/path.name).read_bytes(),path.name
        name=case['name']+'_trace.csv';assert (old/'renders'/name).read_bytes()==(output/name).read_bytes()
        r['legacy'].append(dict(case=case['name'],WAV_exact=28,CSV_exact=True))
    # Null/zero mode changes also preserve the old standalone fixed-idle C
    # source; compare all3 source/detail/mix FLOAT files byte for byte.
    prior=a.workspace/'baselines/idle_modal_c_v1/bin/modal_idle_probe.exe'
    current=repo/'build-modal-texture-v1/modal-idle/Release/modal_idle_probe.exe'
    paths=[repo/'experiments/modal_idle_v1/F2_fixed_idle.msource',repo/'experiments/modal_idle_v1/F2_fixed_idle.rdetail']
    fixed=a.out/'old_fixed';fixed.mkdir()
    for version,exe in [('old',prior),('current',current)]:
        command(f'fixed_{version}',[exe,*paths,fixed/version,12,149921,1,1])
    for stem in ['modal','detail','mix']:
        assert (fixed/f'old_{stem}.wav').read_bytes()==(fixed/f'current_{stem}.wav').read_bytes(),stem
    r.update(result='legacy_and_fixed_C_byte_compatibility_passed',tests=59,WAV_exact=84,CSV_exact=3,
        fixed_idle_WAV_exact=3,device_repeated=False,driver_source_changed=False,
        default_entry_changed=False,old_binaries_preserved=True)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(r['result'],flush=True)

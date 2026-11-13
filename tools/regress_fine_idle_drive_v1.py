"""Compare the separately built fine-idle driver with immutable legacy renders."""
import argparse,subprocess,time,shutil
from pathlib import Path
from research_archive_v1 import sha,load,save
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--out',type=Path,required=True);a=p.parse_args();repo=Path(__file__).resolve().parents[1]
a.out.mkdir(parents=True,exist_ok=False);r=dict(result='running',commands=[],legacy=[])
try:
    shutil.copy2(__file__,a.out/'executed_regression.py')
    build=repo/'build-fine-idle-drive-v1/bin/Release';exe=build/'VslAtlasDrive_probe.exe'
    old=a.workspace/'references/analysis/drive_resonance_v1/before1';snapshot=load(old/'snapshot.json')
    output=a.out/'renders';output.mkdir();shutil.copy2(exe,a.out/exe.name)
    for case in snapshot['cases']:
        options=case['options']+(['--stereo-bed','1'] if case['name'].startswith('E_') else [])
        args=list(map(str,[exe,*case['models'][:2],output/case['name'],*options]))
        before=time.perf_counter();done=subprocess.run(args,cwd=repo,capture_output=True,timeout=240)
        log=a.out/(case['name']+'.log');log.write_bytes(done.stdout+done.stderr)
        r['commands'].append(dict(args=args,return_code=done.returncode,seconds=time.perf_counter()-before,log_sha256=sha(log)))
        save(a.out/'report.json',r);assert done.returncode==0,str(log)
        originals=sorted((old/'renders').glob(case['name']+'_*.wav'));assert len(originals)==28
        for path in originals:
            assert sha(path)==snapshot['files'][path.relative_to(old).as_posix()]
            assert path.read_bytes()==(output/path.name).read_bytes(),path.name
        trace=case['name']+'_trace.csv';assert (old/'renders'/trace).read_bytes()==(output/trace).read_bytes()
        r['legacy'].append(dict(case=case['name'],WAV_exact=28,CSV_exact=True));print(r['legacy'][-1],flush=True)
    r.update(result='passed',WAV_exact=84,CSV_exact=3,optional_fine_idle_disabled=True,old_builds_overwritten=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)

"""Wait on the exact Windows producer handle, then run one independent audit."""
import argparse, ctypes, datetime, json, subprocess, sys, time
from ctypes import wintypes
from pathlib import Path
from research_archive_v1 import load, save, sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('workspace','study','original','audit_out','out'):
        p.add_argument('--'+name.replace('_','-'),type=Path,required=True)
    p.add_argument('--pid',type=int,required=True)
    a=p.parse_args()
    repo=Path(__file__).resolve().parents[1]
    script=repo/'tools/audit_observer_stable_full_v1.py'
    source=load(a.study/'report.json')
    assert source['pid']==a.pid and source['result']=='running'
    assert not a.audit_out.exists()
    a.out.mkdir(exist_ok=False)
    (a.out/'executed_watch.py').write_bytes(Path(__file__).read_bytes())
    r=dict(result='watching',producer_pid=a.pid,watch_pid=__import__('os').getpid(),
        watcher_sha256=sha(__file__),auditor_sha256=sha(script),study=str(a.study),
        audit_out=str(a.audit_out),monitor_snapshots_are_sparse=True)
    save(a.out/'report.json',r)
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
    kernel.OpenProcess.restype=wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes=[wintypes.HANDLE,wintypes.DWORD]
    kernel.WaitForSingleObject.restype=wintypes.DWORD
    kernel.GetExitCodeProcess.argtypes=[wintypes.HANDLE,ctypes.POINTER(wintypes.DWORD)]
    kernel.GetExitCodeProcess.restype=wintypes.BOOL
    kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    kernel.CloseHandle.restype=wintypes.BOOL
    handle=kernel.OpenProcess(0x00100000|0x1000,False,a.pid)
    assert handle,ctypes.get_last_error()
    started=time.monotonic()
    try:
        print('WATCH_PID',r['watch_pid'],'PRODUCER_PID',a.pid,flush=True)
        snapshots=0
        while True:
            status=kernel.WaitForSingleObject(handle,20000)
            assert status in (0,258),(status,ctypes.get_last_error())
            if status==0: break
            value=load(a.study/'progress.json')
            assert value['pid']==a.pid
            snapshot=dict(observed_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                producer_handle_confirmed_live=True,progress=value)
            with (a.out/'observations.jsonl').open('a',encoding='utf-8') as f:
                f.write(json.dumps(snapshot,allow_nan=False)+'\n')
            snapshots+=1
            r.update(snapshots=snapshots,latest_observed=snapshot,watch_elapsed_seconds=time.monotonic()-started)
            save(a.out/'report.json',r)
        exit_code=wintypes.DWORD()
        assert kernel.GetExitCodeProcess(handle,ctypes.byref(exit_code))
        r.update(producer_exit_code=exit_code.value,producer_report_sha256=sha(a.study/'report.json'))
        final=load(a.study/'report.json')
        assert exit_code.value==0 and final['result']=='observer_stable_full_known_measured',final.get('error')
        assert not a.audit_out.exists() and sha(script)==r['auditor_sha256']
        args=[sys.executable,str(script),'--workspace',str(a.workspace),'--study',str(a.study),
            '--original',str(a.original),'--out',str(a.audit_out)]
        with (a.out/'audit_stdout.txt').open('w',encoding='utf-8') as stream:
            child=subprocess.Popen(args,cwd=repo,stdout=stream,stderr=subprocess.STDOUT)
            r.update(result='auditing',audit_pid=child.pid,audit_command=args)
            save(a.out/'report.json',r)
            print('PRODUCER_TERMINAL',exit_code.value,'AUDIT_PID',child.pid,flush=True)
            code=child.wait()
        r.update(audit_exit_code=code,audit_report_sha256=sha(a.audit_out/'report.json'))
        audit=load(a.audit_out/'report.json')
        assert code==0 and audit['result']=='independent_observer_stable_full_passed',audit.get('error')
        r.update(result='observer_stable_full_watch_and_audit_terminal',solver_qualified=audit['solver_qualified'],
            fidelity_qualified=audit['fidelity_qualified'],watch_elapsed_seconds=time.monotonic()-started)
        save(a.out/'report.json',r)
        print(r['result'],'solver',r['solver_qualified'],'fidelity',r['fidelity_qualified'],flush=True)
    except BaseException as error:
        r.update(result='failed',error=repr(error))
        save(a.out/'report.json',r)
        raise
    finally:
        kernel.CloseHandle(handle)


if __name__=='__main__':
    main()

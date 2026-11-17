"""Owned ephemeral workbench; actual browser short fit/render/import checks."""
import argparse
from pathlib import Path
import shutil
import subprocess
import threading
from research_archive_v1 import load,save
from sound_designer.server import create_server


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    out=parser.parse_args().output;out.mkdir(parents=True,exist_ok=False)
    repo=Path(__file__).resolve().parents[1];data=Path('E:/VehicleSoundLab')
    node=Path('C:/Users/mlslabs-06/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe')
    report=dict(result='running',goal_complete=False,timbre_accepted=False)
    for path in [Path(__file__),repo/'tools/verify_short_event_workbench_web_v1.cjs',
                 *sorted((repo/'tools/sound_designer/web').glob('events.*')),
                 repo/'tools/sound_designer/web/event_candidates.js']:
        target=out/'exact_sources'/path.relative_to(repo);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
    server=create_server(repo,out/'workspace',0);thread=threading.Thread(target=server.serve_forever);thread.start()
    try:
        run=subprocess.run([str(node),str(repo/'tools/verify_short_event_workbench_web_v1.cjs'),
            str(node.parents[1]/'node_modules'),str(out),
            str(data/'references/analysis/short_event_scan_v1/probe2/burst-1049.wav'),
            'http://127.0.0.1:'+str(server.server_address[1])],cwd=repo,capture_output=True,timeout=180,creationflags=0x08000000)
        (out/'stdout.log').write_bytes(run.stdout);(out/'stderr.log').write_bytes(run.stderr)
        assert run.returncode==0,run.stderr.decode(errors='replace')
        report=load(out/'report.json')
    finally:
        server.shutdown();server.server_close();thread.join(timeout=5)
        if (out/'report.json').is_file():report=load(out/'report.json')
        report.update(own_server_closed=not thread.is_alive(),goal_complete=False,timbre_accepted=False)
        save(out/'report.json',report)
    assert not thread.is_alive();print(report,flush=True)


if __name__=='__main__':main()

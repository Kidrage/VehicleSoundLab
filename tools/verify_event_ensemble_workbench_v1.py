"""Run a real browser against an owned temporary event workbench."""
import argparse
from pathlib import Path
import shutil
import subprocess
import threading
from research_archive_v1 import load,save,sha
from sound_designer.server import create_server


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    out=parser.parse_args().output;out.mkdir(parents=True,exist_ok=False)
    repo=Path(__file__).resolve().parents[1];data=Path('E:/VehicleSoundLab')
    node=Path('C:/Users/mlslabs-06/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe')
    for path in [Path(__file__),repo/'tools/verify_event_ensemble_workbench_web_v1.cjs',
                 *sorted((repo/'tools/sound_designer/web').glob('events.*'))]:
        target=out/'exact_sources'/path.relative_to(repo);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
    fixtures={name:load(data/'references/analysis/event_ensemble_v1/probe1'/name/'source-job.json')
              for name in ('B_rank6','B_rank3')}
    save(out/'fixtures.json',fixtures)
    save(out/'fixture-bindings.json',{name:sha(Path(job['source'])) for name,job in fixtures.items()})
    server=create_server(repo,out/'workspace',0);thread=threading.Thread(target=server.serve_forever);thread.start()
    report=dict(result='running',goal_complete=False,timbre_accepted=False)
    try:
        run=subprocess.run([str(node),str(repo/'tools/verify_event_ensemble_workbench_web_v1.cjs'),
            str(node.parents[1]/'node_modules'),str(out),'http://127.0.0.1:'+str(server.server_address[1])],
            cwd=repo,capture_output=True,timeout=240,creationflags=0x08000000)
        (out/'stdout.log').write_bytes(run.stdout);(out/'stderr.log').write_bytes(run.stderr)
        if (out/'report.json').is_file():report=load(out/'report.json')
        assert run.returncode==0,run.stderr.decode(errors='replace')
    except Exception as error:
        report.update(result='failed',wrapper_error=repr(error));raise
    finally:
        server.shutdown();server.server_close();thread.join(timeout=5)
        report.update(own_server_closed=not thread.is_alive(),goal_complete=False,timbre_accepted=False)
        save(out/'report.json',report)
    assert not thread.is_alive();print(report,flush=True)


if __name__=='__main__':main()

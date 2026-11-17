"""Audit unchanged runtime and freeze offline candidate-workbench delivery delta."""
import argparse
from datetime import datetime,timezone
from functools import partial
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
import json
from pathlib import Path
import shutil
import subprocess
import sys
import threading
from event_authoring.audio import sha
from event_designer.workspace import EventWorkspace
from event_designer.package import write_json
from startup_response_evidence_v1 import verify
from vehicle_controller.event_profiles import document


def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--freeze',type=Path,required=True);a=p.parse_args()
    repo=Path(__file__).resolve().parents[1];data=Path('E:/VehicleSoundLab')
    work=data/'references/analysis/A_exterior_event_v1'
    result=read(work/'verification1/report.json');regression=read(work/'context-regression1/report.json')
    assert result['result']==regression['result']=='passed'
    binding=read(data/'references/analysis/dna_controller_v1/verification2/source_binding.json')
    verify(repo,binding)
    previous=read(repo/'research/dna_controller_v1_verification.json')
    assert len(previous['voices_unchanged'])==89
    for row in previous['voices_unchanged']:assert sha(repo/row['path'])==row['sha256'],row['path']
    for row in previous['binaries'].values():assert sha(row['path'])==row['sha256']
    native_files=[r for r in binding['files'] if Path(r['path']).suffix in ('.c','.h')]
    for file in (work/'verification1/projects').glob('*/parameters.json'):raise AssertionError('Unexpected loose export')
    bundles=list((work/'verification1/projects').glob('*/*/parameters.json'));assert bundles
    for file in bundles:
        value=read(file);assert document(value)==value['document']
    # Exercise the changed CLI wrapper, preserving the exact original report rows.
    cli=subprocess.run([sys.executable,str(repo/'tools/scan_approved_event_region.py'),
        '--source','A','--range','190','285','--range','300','355','--output',str(work/'scan2')],
        cwd=repo,capture_output=True,timeout=60,creationflags=0x08000000)
    (work/'scan2.stdout.log').write_bytes(cli.stdout);(work/'scan2.stderr.log').write_bytes(cli.stderr)
    assert cli.returncode==0,cli.stderr.decode(errors='replace')
    old,new=read(work/'scan1/report.json'),read(work/'scan2/report.json')
    assert old['candidates']==new['candidates'] and old['blocks']==new['blocks']
    assert old['detector']==new['detector'] and old['source_sha256']==new['source_sha256']
    review=read(work/'review1/report.json')
    ws=EventWorkspace(repo,data/'designs/events');project=ws.view(review['project_id'])
    assert not project['document'] and project['context_matches_selection']
    assert not review['physical_identity_confirmed'] and not review['fit_performed']
    # Bounded static preview verification, always closed; never restart an app.
    class Quiet(SimpleHTTPRequestHandler):
        def log_message(self,*args):pass
    web=work/'review-web1';web.mkdir()
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(Quiet,directory=str(data)))
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    node=Path('C:/Users/mlslabs-06/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe')
    try:
        run=subprocess.run([str(node),str(repo/'tools/verify_A_exterior_event_review_v1.cjs'),
            str(node.parents[1]/'node_modules'),str(web),
            'http://127.0.0.1:'+str(server.server_address[1])+'/references/analysis/A_exterior_event_v1/review1/index.html'],
            cwd=repo,capture_output=True,timeout=60,creationflags=0x08000000)
        (web/'stdout.log').write_bytes(run.stdout);(web/'stderr.log').write_bytes(run.stderr)
        assert run.returncode==0,run.stderr.decode(errors='replace')
    finally:server.shutdown();server.server_close();thread.join(timeout=5)
    assert not thread.is_alive() and read(web/'report.json')['result']=='passed'
    subprocess.run(['git','diff','--check'],cwd=repo,check=True)
    base=data/'baselines/dna_controller_v1/delivery1';assert (base/'manifest.json').is_file()
    summary=dict(schema='vsl.event-candidate-workbench-milestone/1',result='passed',
        previous_goal_turn='no_progress',current_goal_turn='progress',verification=result,context_regression=regression,
        static_review=read(web/'report.json'),original_C_H_unchanged=len(native_files),voices_unchanged=89,
        binaries=previous['binaries'],formal_event_mask=6,CLI_original92_exact=True,
        controller_parameter_import_compatible=True,diagnostic_project_id=project['id'],
        no_new_timbre_accepted=True,no_formal_profile_promotion=True,runtime_C_changed=False,
        new_download=False,commit_or_push=False,persistent_app_restarted=False,
        owned_test_services_closed=True,goal_complete=False,
        unresolved=['startup listening','confirmed full-band afterfire','other independent event timbres','full RPM/load/state quality'],
        base_freeze=str(base),base_manifest_sha256=sha(base/'manifest.json'),freeze=str(a.freeze))
    write_json(repo/'research/event_candidates_v1_verification.json',summary)
    files=['AGENTS.md','handoff/当前代码阅读入口.md','handoff/事件候选扫描与工作台V3.md',
        'research/A_exterior_event_v1_plan.json','research/A_exterior_event_v1_timeline.json','research/event_candidates_v1_verification.json',
        'tools/event_authoring/scan.py','tools/scan_approved_event_region.py','tools/event_designer/candidates.py',
        'tools/event_designer/workspace.py','tools/event_designer/package.py','tools/sound_designer/server.py',
        'tools/sound_designer/web/event_candidates.js','tools/sound_designer/web/events.js',
        'tools/sound_designer/web/events.html','tools/sound_designer/web/events.css',
        'tools/verify_event_candidates_v1.py','tools/verify_event_candidates_ui_v1.cjs',
        'tools/build_A_exterior_event_review_v1.py','tools/verify_A_exterior_event_review_v1.cjs',
        'tools/finalize_event_candidates_v1.py']
    a.freeze.mkdir(parents=True,exist_ok=False)
    for name in files:
        target=a.freeze/'repo'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,target)
    shutil.copytree(work,a.freeze/'evidence',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    shutil.copytree(ws.root/project['id'],a.freeze/'diagnostic-project'/project['id'])
    write_json(a.freeze/'runtime-binding.json',binding)
    (a.freeze/'README.md').write_text('''# 事件候选扫描工作台 V3 增量

基于 dna_controller_v1/delivery1 的显式增量；该基础清单进一步指向其原基础链。恢复时在基础副本上覆盖repo。diagnostic-project中的工程可放入数据根designs/events。evidence包含本轮原计划、旧/新扫描、原声/附近画面、网页/原C回归和静态核查页。

本轮没有新增C、ABI、正式音色或空间渲染，不需要替换V8/事件V2 DLL。runtime-binding.json绑定原二进制及完整原C/控制/资产来源。扫描为非实时作者工具；单独的本增量不宣称可脱离基础构建。启动听评、真实全频回火及其他状态音色仍未完成。
''',encoding='utf-8')
    rows=[dict(path=f.relative_to(a.freeze).as_posix(),bytes=f.stat().st_size,sha256=sha(f))
          for f in sorted(a.freeze.rglob('*')) if f.is_file()]
    write_json(a.freeze/'manifest.json',dict(schema='vsl.event-candidate-workbench-delta/1',
        created=datetime.now(timezone.utc).isoformat(),base_freeze=str(base),
        base_manifest_sha256=sha(base/'manifest.json'),goal_complete=False,files=rows))
    print(json.dumps(dict(result='frozen',C_H_unchanged=len(native_files),voices_unchanged=89,
        files=len(rows),bytes=sum(r['bytes'] for r in rows),path=str(a.freeze))))


if __name__=='__main__':main()

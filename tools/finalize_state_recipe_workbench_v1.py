"""Bind the new authoring workflow to tests and unchanged V9 runtime assets."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
from research_archive_v1 import sha, save


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--freeze',type=Path,required=True)
    args=parser.parse_args();repo=Path(__file__).resolve().parents[1];data=Path('E:/VehicleSoundLab')
    work=data/'references/analysis/state_recipe_workbench_v1';base=data/'baselines/state_dna_controller_v1/delivery1'
    native=read(work/'verification1/report.json');web=read(work/'web1/verification.json')
    regression=read(work/'single-state-regression1/verification.json')
    assert native['result']==web['result']==regression['result']=='passed'
    assert len(native['actual_native_C'])==3 and native['invalid_preserves_recipe']==9
    assert web['downloaded_parameters_actual_C'] and web['own_service_closed']
    assert web['browser']['driver_not_launched'] and web['browser']['no_autoplay']
    assert regression['owned_service_closed'] and len(regression['checks'])==2
    # The backend run predates only shared navigation and verification-source
    # additions. Verify its executed backend contracts, and every final web input.
    earlier=read(work/'verification1/source_binding.json')
    backend=('tools/sound_designer/state_recipes.py','tools/sound_designer/workspace.py',
             'tools/sound_designer/models.py','tools/vehicle_controller/dna_bank.py')
    for name in backend:
        assert sha(repo/name)==earlier[name],name
    for name,expected in read(work/'web1/source_binding.json').items():
        assert sha(repo/name)==expected,name
    for name in ('tools/verify_state_recipe_workbench_web_v1.py','tools/verify_state_recipe_workbench_web_v1.cjs'):
        evidence=work/'web1'/('executed_verification.py' if name.endswith('.py') else Path(name).name)
        assert sha(repo/name)==sha(evidence),name
    prior=read(base/'manifest.json');old={x['path'][5:]:x for x in prior['files'] if x['path'].startswith('repo/')}
    unchanged=[]
    for folder in ('src','modules','experiments/vehicle_source_v1'):
        for path in (repo/folder).rglob('*'):
            if path.is_file() and path.suffix in ('.c','.h'):
                name=path.relative_to(repo).as_posix()
                assert name in old and sha(path)==old[name]['sha256'],name
                unchanged.append(name)
    voices=[]
    for path in sorted((repo/'voices').rglob('*')):
        if path.is_file():
            name=path.relative_to(repo).as_posix();assert sha(path)==old[name]['sha256'],name
            voices.append(name)
    assert len(voices)==89
    dll=repo/'build-vehicle-source-v9/bin/Release/vsl_source_bridge.dll'
    binary=next(x for x in prior['files'] if x['path']=='binaries/source-v9/vsl_source_bridge.dll')
    assert sha(dll)==binary['sha256']==native['bridge_sha256']==web['bridge_sha256']
    subprocess.run(['git','diff','--check'],cwd=repo,check=True)
    milestone=dict(schema='vsl.state-recipe-workbench-milestone/1',result='passed',
        previous_goal_turn='progress',current_goal_turn='progress',native=native,web=web,old_single_state=regression,
        runtime_C_H_unchanged=unchanged,voices_unchanged=voices,bridge_sha256=sha(dll),
        base_freeze=str(base),base_manifest_sha256=sha(base/'manifest.json'),freeze=str(args.freeze),
        persistent_app_restarted=False,owned_services_browser_closed=True,new_download=False,commit_or_push=False,
        optimization_or_ADI=False,spatial_added=False,goal_complete=False,new_timbre_accepted=False,
        unresolved=['startup hearing','confirmed full-band afterfire','other event timbres','full RPM/load/state quality'])
    save(repo/'research/state_recipe_workbench_v1_verification.json',milestone)
    args.freeze.mkdir(parents=True,exist_ok=False)
    selected=('tools/sound_designer','tools/verify_state_recipe_workbench_v1.py',
        'tools/verify_state_recipe_workbench_web_v1.py','tools/verify_state_recipe_workbench_web_v1.cjs',
        'tools/finalize_state_recipe_workbench_v1.py','tools/research_archive_v1.py',
        'handoff/工作台车辆DNA配方V1.md','handoff/当前代码阅读入口.md',
        'research/state_recipe_workbench_v1_verification.json','AGENTS.md')
    for name in selected:
        source,target=repo/name,args.freeze/'repo'/name;target.parent.mkdir(parents=True,exist_ok=True)
        if source.is_dir():shutil.copytree(source,target,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        else:shutil.copy2(source,target)
    shutil.copytree(work,args.freeze/'evidence',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    (args.freeze/'README.md').write_text(
        '# 工作台车辆 DNA 配方 V1 冻结增量\n\n'
        '基于state_dna_controller_v1/delivery1及其manifest基础链。恢复基础后覆盖本增量repo；'
        '底层C、89个声源文件和V9二进制保持原版本。本增量不能脱离基础独立构建。\n\n'
        'verification1为作者参数/历史/错误拒绝及三组实际C精确对照；web1为真实Chrome和HTTP下载，'
        '下载参数也经C采用；single-state-regression1覆盖旧单状态导出。自有有界服务和浏览器已关闭，'
        '不启动常驻控制器，旧常驻服务未更新。没有新音色认可、新素材下载或推送。\n\n'
        '此交付完善四状态主DNA作者工具，不代表真实启动/全频回火/其他事件和完整整车标定完成。'
        '渲染由外部仓库承担，本轮没有DSP优化或ADI性能验证。\n',encoding='utf-8')
    subprocess.run(['git','diff','--binary','--output='+str(args.freeze/'working-tree.patch')],cwd=repo,check=True)
    files=[dict(path=p.relative_to(args.freeze).as_posix(),bytes=p.stat().st_size,sha256=sha(p))
        for p in sorted(args.freeze.rglob('*')) if p.is_file()]
    save(args.freeze/'manifest.json',dict(schema='vsl.state-recipe-workbench-delta-freeze/1',
        created=datetime.now(timezone.utc).isoformat(),base_freeze=str(base),base_manifest_sha256=sha(base/'manifest.json'),
        goal_complete=False,files=files))
    print(json.dumps(dict(result='frozen',files=len(files),bytes=sum(x['bytes'] for x in files),path=str(args.freeze))),flush=True)


if __name__=='__main__':main()

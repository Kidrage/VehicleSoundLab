"""Verify the study selector correction while binding unchanged completed DSP proof."""
import argparse,hashlib,json,shutil,subprocess,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for name in ('workspace','build','verification','out'):p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];a.out.mkdir(parents=True,exist_ok=False)
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
from PIL import Image
sha=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest()
r=dict(result='running',source_proof=str(a.verification/'report.json'),source_proof_sha256=sha(a.verification/'report.json'),sources={},ui={})
ui={'experiments/atlas_monitor_v1/ui.c','experiments/drive_resonance_v1/ui_checks.c'}
try:
    v=json.loads((a.verification/'report.json').read_text(encoding='utf-8'));assert v['result']=='stereo_driver_technical_pass'
    for name,digest in v['sources'].items():
        if name not in ui|{'tools/verify_stereo_drive_v1.py'}:assert sha(repo/name)==digest,name
    for name,digest in v['evidence_sha256'].items():assert sha(a.verification/name)==digest,name
    for name in ('VslAtlasDrive_probe','VslAtlasTake_render','VslDriveResonance_device'):
        assert sha(a.build/'bin/Release'/f'{name}.exe')==sha(a.verification/'bin'/f'{name}.exe')
    assert sha(a.build/'CMakeCache.txt')==sha(a.verification/'CMakeCache.after_build.txt')
    for name in sorted(ui|{'tools/verify_stereo_drive_v1.py','tools/verify_stereo_drive_ui_v1.py'}):
        target=a.out/'exact_sources'/name;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(repo/name,target);r['sources'][name]=sha(repo/name)
    shutil.copy2(a.build/'bin/Release/VslAtlasMonitor.exe',a.out/'VslAtlasMonitor.exe')
    for flag in ('--resonant-study','--stereo-resonant-study'):
        folder=a.out/flag[2:];folder.mkdir()
        proc=subprocess.run([str(a.out/'VslAtlasMonitor.exe'),flag,'--ui-check',str(folder/'ui.json')],cwd=repo,capture_output=True,timeout=60)
        (folder/'command.log').write_bytes(proc.stdout+proc.stderr);assert proc.returncode==0
        u=json.loads((folder/'ui.json').read_text());assert u['result']=='pass'
        Image.open(folder/'ui.json.bmp').convert('RGB').save(folder/'window.png');r['ui'][flag]=u
    r.update(result='ui_selector_technical_pass',DSP_device_binaries_exact=True,Ctests_reused=53)
finally:
    r['evidence_sha256']={v.relative_to(a.out).as_posix():sha(v) for v in a.out.rglob('*') if v.is_file() and 'exact_sources' not in v.parts}
    (a.out/'report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(result=r['result'])))

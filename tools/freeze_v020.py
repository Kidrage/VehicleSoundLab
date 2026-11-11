"""Freeze reviewed DSP020 code/binaries/evidence; never alter earlier snapshots."""
import json,shutil
from runtime_review import ROOT,sha
OUT=ROOT/'baselines/v0.20.0'
def read(path):return json.loads(path.read_text(encoding='utf-8'))
def main():
    if OUT.exists():raise SystemExit('Preserve completed DSP020 snapshot.')
    native=read(ROOT/'renders/app0.20.0/native_verification.json')
    render=read(ROOT/'renders/v0.20.0/verification.json')
    browser=read(ROOT/'renders/v0.20.0/browser_qa.json')
    assert native['result']=='pass' and native['ctest_count']==23 and render['dsp']=='0.20.0' and browser['loads']==12 and not browser['errors']
    assert sha(ROOT/'build-v020/Release/VehicleSoundLab.exe')==native['executable_sha256']
    for name,digest in render['files'].items():assert sha(ROOT/'renders/v0.20.0'/name)==digest,name
    old={};verified_files=0
    for path in sorted((ROOT/'baselines').glob('*/manifest.json')):
        m=read(path);old[path.parent.name]=sha(path)
        for item in m['files']:
            # Every established native/experiment snapshot uses a list of paths.
            assert sha(path.parent/item['path'])==item['sha256'],(path.parent.name,item['path'])
            verified_files+=1
    for item in read(ROOT/'baselines/app0.19.1/manifest.json')['files']:
        if item['path'].startswith('bin/'):
            assert sha(ROOT/'build-app0191/Release'/item['path'][4:])==item['sha256']
    # Kernel source is an exact mechanical namespace move of the frozen recipe.
    for suffix in ['c','h']:
        text=(ROOT/f'experiments/firing_pulse_v1/kernel.{suffix}').read_text(encoding='utf-8')
        for a,b in [('VSL_FIRING_PULSE_KERNEL_H','VSL_PULSE_KERNEL_H'),('"kernel.h"','"pulse_kernel.h"'),('"profile.h"','"profiles/firing_source.h"'),('FP_OVERSAMPLE','VSL_PULSE_OVERSAMPLE'),('FP_TAPS','VSL_PULSE_TAPS'),('FP_VOICES','VSL_PULSE_VOICES'),('FpVoice','VslPulseVoice'),('FpKernel','VslPulseKernel'),('fp_','vsl_pulse_')]:text=text.replace(a,b)
        assert text==(ROOT/f'src/core/pulse_kernel.{suffix}').read_text(encoding='utf-8')
    OUT.mkdir()
    def copy(path,name):
        dest=OUT/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,dest)
    for folder in ['src','tests']:shutil.copytree(ROOT/folder,OUT/folder)
    names=['README.md','AGENTS.md','CMakeLists.txt','build.ps1','Launch-current.cmd','Launch-ui.cmd','Launch-v020.cmd','Launch-firing-source.cmd','Launch-app0191.cmd',
        'research/V020实时燃烧声源.md','research/V020燃烧声源试听.html','research/DE素材可用性V1.md','research/goal_progress_v020.json','research/direction_decision_20261110.json',
        'tools/integrate_firing_source_v020.py','tools/integrate_firing_source_ui_v020.py','tools/check_v020_native.py','tools/review_v020.py','tools/verify_v020_ui.cjs','tools/freeze_v020.py',
        'tools/v016_probe.c','tools/runtime_review.py','tools/review_audit.py','tools/seekable_review_player_v1.js','tools/firing_pulse_page.html',
        'tools/download_calibration_approved_v1.py','tools/inspect_DE_v1.py','tools/inspect_DE_details_v1.py','tools/register_DE_observations_v1.py','tools/reference_segments.py',
        'references/segments_v1.json','references/approval_manifest.json']
    for name in names:copy(ROOT/name,name)
    for folder in ['app0.20.0','v0.20.0']:
        for path in (ROOT/'renders'/folder).rglob('*'):
            if path.is_file() and path.suffix in ['.json','.log','.png','.ini','.vsltake']:
                copy(path,'review/'+folder+'/'+path.relative_to(ROOT/'renders'/folder).as_posix())
    binaries={}
    for path in (ROOT/'build-v020/Release').iterdir():
        if path.suffix in ['.exe','.lib']:copy(path,'bin/'+path.name);binaries[path.name]=sha(path)
    files=[dict(path=p.relative_to(OUT).as_posix(),sha256=sha(p)) for p in sorted(OUT.rglob('*')) if p.is_file()]
    manifest=dict(application='0.20.0',DSP='0.20.0',seed=48271,take_schema=5,parameter_fields=38,
        status='Approved event-source route integrated and technically verified; target timbre/naturalness not subjectively accepted. Broad goal incomplete.',
        previous_snapshot_manifest_identities=old,previous_snapshot_files_verified=verified_files,binaries=binaries,
        media='Reference media and listening WAVs remain at workspace locations; never uploaded. This snapshot copies code, take inputs and evidence only.',files=files)
    (OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    for item in files:assert sha(OUT/item['path'])==item['sha256']
    print(json.dumps(dict(frozen='v0.20.0',files=len(files),previous_snapshots_verified=len(old),previous_files_verified=verified_files,manifest_sha256=sha(OUT/'manifest.json')),indent=2))
if __name__=='__main__':main()

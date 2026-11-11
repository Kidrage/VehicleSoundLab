"""One-time snapshot of the standalone audition; raw renders remain hash-bound."""
import json
import shutil
from runtime_review import ROOT,sha

def main():
    target=ROOT/'baselines/firing_pulse_v1'
    if target.exists():raise SystemExit('Preserve existing firing_pulse_v1 snapshot.')
    out=ROOT/'renders/firing_pulse_v1'
    required=['results.json','independent_verification.json','browser_qa.json','ctest.txt']
    assert all((out/name).is_file() for name in required)
    target.mkdir(parents=True)
    mappings=[]
    for path in (ROOT/'experiments/firing_pulse_v1').glob('*'):
        if path.is_file():mappings.append((path,path.relative_to(ROOT)))
    for name in ['render_firing_pulse.py','verify_firing_pulse.py','verify_firing_pulse_ui.cjs','freeze_firing_pulse.py',
                 'firing_pulse_page.html','seekable_review_player_v1.js','runtime_review.py']:
        mappings.append((ROOT/'tools'/name,'tools/'+name))
    for name in ['逐缸压力源实验V1.md','逐缸压力源试听V1.html','goal_progress_firing_pulse_v1.json']:
        mappings.append((ROOT/'research'/name,'research/'+name))
    for path in (ROOT/'build-experiment-firing-pulse/Release').glob('*'):
        if path.suffix in ['.lib','.exe']:mappings.append((path,'bin/'+path.name))
    for name in required+['desktop.png','mobile.png']:
        mappings.append((out/name,'review/'+name))
    for path in out.glob('*/audition_*.wav'):mappings.append((path,'review/'+path.relative_to(out).as_posix()))
    for source,relative in mappings:
        dest=target/relative;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,dest)
    data=dict(version='firing_pulse_v1',base_runtime='0.19.0',seed=48271,subjective_acceptance=False,
        dependencies={name:sha(ROOT/name) for name in ['baselines/v0.19.0/manifest.json','baselines/app0.19.1/manifest.json',
            'baselines/v0.19.0/bin/vsl_core.lib','renders/event_color_v1/reference_A_exterior_blips.wav']},
        files=[dict(path=p.relative_to(target).as_posix(),sha256=sha(p)) for p in sorted(target.rglob('*')) if p.is_file()],
        external_render_files={p.relative_to(ROOT).as_posix():sha(p) for p in out.rglob('*') if p.is_file()})
    (target/'manifest.json').write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf-8')
    for item in data['files']:assert sha(target/item['path'])==item['sha256']
    print(json.dumps(dict(snapshot=str(target),files=len(data['files']),manifest_sha256=sha(target/'manifest.json'))))

if __name__=='__main__':main()

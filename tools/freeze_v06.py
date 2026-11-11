"""Freeze V0.6 runtime, selected listening assets and local technical evidence.

The review HTML and approved source recordings remain in the workspace at their
original paths. This snapshot preserves runtime/research evidence, not a new
standalone media distribution.
"""
from pathlib import Path
import hashlib
import json
import shutil

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'baselines/v0.6.0'
RENDER = ROOT/'renders/v0.6.0'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def copy(source, destination):
    target = OUT/destination
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT/source, target)


def main():
    if OUT.exists():
        raise SystemExit('V0.6 exists: preserve it and use a new version.')
    audit = json.loads((RENDER/'workspace_audit.json').read_text())
    assert audit['result'] == 'pass' and audit['version'] == '0.6.0' and audit['ctest_count'] == 8
    for name, digest in audit['source_code'].items():
        assert sha(ROOT/name) == digest, name
    for name, digest in audit['analysis']['artifacts'].items():
        assert sha(ROOT/name) == digest, name
    assert sha(ROOT/'build-v06/Release/vsl_render.exe') == audit['dna_pipeline']['renderer_sha256']
    OUT.mkdir()
    for folder in ['src','tests']:
        shutil.copytree(ROOT/folder, OUT/folder)
    for name in ['CMakeLists.txt','build.ps1','Launch.cmd','README.md','AGENTS.md']:
        copy(name, name)
    for name in ['VehicleSoundLab.exe','vsl_render.exe']:
        copy('build-v06/Release/'+name, 'bin/'+name)
    for name in ['V06点火几何与素材核查.md','goal_progress_v06.json','state_evidence_v02.json']:
        copy('research/'+name, 'research/'+name)
    for name in ['render_v06_review.py','runtime_review.py','make_v06_review.py',
                 'analyze_bank_geometry.py','verify_v06.py','freeze_v06.py',
                 'check_dna_pipeline.py','verify_review_player.cjs','capture_preview.py']:
        copy('tools/'+name, 'tools/'+name)
    for name in ['verification.json','workspace_audit.json','ctest.xml','ui_smoke.json',
                 'browser_qa.json','ui_native_preview.png','ui_detail.png',
                 'listening_desktop.png','listening_mobile.png']:
        copy('renders/v0.6.0/'+name, 'diagnostics/'+name)
    copy('renders/v0.6.0/dna_check/dna_pipeline_check.json','diagnostics/dna_pipeline_check.json')
    for path in sorted(RENDER.glob('audition_*.wav')):
        copy(path.relative_to(ROOT), 'renders/'+path.name)
    for name in ['drive_v06.wav','downshift_v06.wav','engineering_110Hz.dna']:
        copy('renders/v0.6.0/'+name, 'renders/'+name)
    for path in sorted(RENDER.glob('*.csv')):
        copy(path.relative_to(ROOT), 'renders/'+path.name)
    # Cached complete source pages are small enough to retain with the ledger.
    ledger = json.loads((ROOT/'references/analysis/bank_geometry_v1/technical_evidence.json').read_text(encoding='utf-8'))
    for item in [*ledger['primary'],ledger['target_link'],ledger['rejected_number']]:
        path = Path(item['local_html'])
        assert sha(ROOT/path) == item['sha256']
        copy(path, path)
        copy(path.with_suffix('.txt'), path.with_suffix('.txt'))
    for name in ['audi_52_engine.provenance.json','audi_2019_engine.provenance.json','evo_52.html.provenance.json']:
        copy('research/technical_sources/'+name,'research/technical_sources/'+name)
    for name in audit['analysis']['artifacts']:
        copy(name, name)
    files = [dict(path=str(p.relative_to(OUT)).replace('\\','/'),sha256=sha(p))
             for p in sorted(OUT.rglob('*')) if p.is_file()]
    manifest = dict(version='v0.6.0',seed=48271,sample_rate=48000,
        status='Frozen review: 5.2 family common-pin geometry and actual exported phase checks. Broad sound/driving objective remains active.',
        upstream_revision='ac2b37d8639027d79934a2023cf8d1d37d3b2f96',
        review_workspace_path='research/V06试听.html',
        review_html_sha256=sha(ROOT/'research/V06试听.html'),
        source_media='Approved originals and analysis masters retained at original workspace paths; not duplicated here.',
        files=files)
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    for item in files:
        assert sha(OUT/item['path']) == item['sha256'], item['path']
    print('Frozen V0.6:',len(files),'files verified')


if __name__ == '__main__':
    main()

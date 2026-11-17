"""Capture a source-isolated startup/idle candidate with the actual current C DLL."""
import argparse
import json
from pathlib import Path
import shutil

from event_authoring.audio import sha
from event_designer.package import write_json
from startup_handoff_v1.session import generate
from vehicle_controller.native import Bridge


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--crank-seconds', type=float)
    p.add_argument('--catch-level', type=float)
    p.add_argument('--library', type=Path)
    args = p.parse_args()
    repo = Path(__file__).resolve().parents[1]
    source = Path('E:/VehicleSoundLab/renders/startup_timbre_v1/delivery1/startup-candidate.recipe.json')
    bridge = Bridge(repo, args.library)
    result = generate(bridge, json.loads(source.read_text(encoding='utf-8')), args.output,
                      args.crank_seconds, args.catch_level)
    shutil.copy2(source, args.output/'original-preset4.json')
    paths = [Path(__file__), repo/'tools/startup_handoff_v1/session.py',
             repo/'modules/vehicle_source/source.c', repo/'modules/vehicle_source/control.c',
             repo/'modules/atlas_drive/render.c', repo/'src/drive/lifecycle.c',
             repo/'src/core/orchestrator.c', repo/'modules/event_control/policy.c']
    write_json(args.output/'provenance.json', dict(
        source_preset=str(source), source_preset_sha256=sha(source),
        bridge_path=str(bridge.path), bridge_sha256=bridge.sha256,
        current_source_files=[dict(path=str(path), sha256=sha(path)) for path in paths],
        reauthored_with_current_schema=True, old_document_not_directly_loaded=True,
        crank_seconds=args.crank_seconds, catch_level=args.catch_level,
        room_processing=False, normalization=False, pc_timing_is_not_ADI_MCPS=True))
    print(json.dumps(dict(result=result['result'], output=str(args.output),
                          checks=result['checks']), ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()

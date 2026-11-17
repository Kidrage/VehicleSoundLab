"""Replay a source-controller take into float WAV and isolated native stems."""
import argparse
import json
from pathlib import Path

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('take',type=Path)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--mix-only',action='store_true');a=parser.parse_args()
    from vehicle_controller.native import Bridge
    from vehicle_controller import take
    from vehicle_controller.render import export
    bridge=Bridge(Path(__file__).resolve().parents[1]);print(json.dumps(export(bridge,take.read(a.take,bridge),a.output,not a.mix_only),ensure_ascii=False,indent=2))

if __name__=='__main__':main()

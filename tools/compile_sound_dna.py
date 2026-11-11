"""Compile a stable-pitch WAV into a reusable procedural sound DNA profile."""
from runtime_review import ROOT
from sound_dna.profile import compile_file
import argparse
import json
from pathlib import Path


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--root-hz',type=float,required=True);p.add_argument('--name',required=True)
    p.add_argument('--harmonics',type=int,default=96);p.add_argument('--components',type=int,default=12);a=p.parse_args()
    print(json.dumps(compile_file(a.source,a.out,a.root_hz,a.name,a.harmonics,a.components),ensure_ascii=False,indent=2))


if __name__=='__main__':main()

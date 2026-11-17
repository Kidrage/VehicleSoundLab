"""Build the isolated startup-to-idle C comparison page."""
import argparse
from pathlib import Path
from startup_handoff_v1.review import build

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();build(args.root,args.output)
    print(args.output,flush=True)

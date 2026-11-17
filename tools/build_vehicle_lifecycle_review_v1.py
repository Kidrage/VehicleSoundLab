"""Build a static, source-only full-lifecycle listening page."""
import argparse
from pathlib import Path
import sys


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    sys.path.insert(0,'E:/VehicleSoundLab/tools/python_deps')
    from vehicle_scenarios.review import build
    value=build(args.capture,args.output)
    print(str(args.output/'index.html'))

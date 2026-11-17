"""Launch the independent dry-source controller window."""
import argparse
from pathlib import Path

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace',type=Path,default=Path('E:/VehicleSoundLab/controller_takes'))
    parser.add_argument('--ready-file',type=Path)
    parser.add_argument('--library',type=Path,help='Explicit frozen C bridge for its original strict-identity takes')
    args=parser.parse_args()
    from vehicle_controller.ui import run
    run(Path(__file__).resolve().parents[1],args.workspace,args.ready_file,args.library)

if __name__=='__main__':main()

"""Launch the local sound-design UI and reuse existing analysis/C rendering."""
import argparse
import os
from pathlib import Path
import sys
import threading
import webbrowser


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace',type=Path,default=Path('E:/VehicleSoundLab'))
    parser.add_argument('--port',type=int,default=8791)
    parser.add_argument('--no-browser',action='store_true')
    a=parser.parse_args()
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'): os.environ[key]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    from sound_designer.server import serve
    repo=Path(__file__).resolve().parents[1]
    if not a.no_browser:
        threading.Timer(1.5,lambda:webbrowser.open(f'http://127.0.0.1:{a.port}')).start()
    serve(repo,a.workspace/'designs',a.port)


if __name__=='__main__': main()

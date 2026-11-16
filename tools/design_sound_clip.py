"""Run one labeled clip job without a web server; same authoring and C renderer."""
import argparse
import json
import os
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('job', type=Path, help='vsl.sound-design-job/1 JSON')
    parser.add_argument('--out', required=True, type=Path, help='New output directory')
    parser.add_argument('--workspace', type=Path, default=Path('E:/VehicleSoundLab'))
    parser.add_argument('--inspect', action='store_true', help='Analysis only, even with confirmed root')
    args = parser.parse_args()
    for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[key] = '2'
    sys.path.insert(0, str(args.workspace / 'tools/python_deps'))
    from sound_designer.jobs import execute
    try:
        result = execute(Path(__file__).resolve().parents[1], args.workspace, args.job, args.out, args.inspect)
    except FileExistsError:
        result = dict(status='failed', error='输出目录已存在，请使用新目录；原结果保留。', exit_code=2)
    except Exception as error:
        result = dict(status='failed', error=str(error), exit_code=2)
    # ASCII JSON remains readable to automation on Windows code pages.
    print(json.dumps(result, ensure_ascii=True, allow_nan=False), flush=True)
    return result['exit_code']


if __name__ == '__main__':
    raise SystemExit(main())

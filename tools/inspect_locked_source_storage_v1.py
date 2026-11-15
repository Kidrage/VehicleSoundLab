"""Read-only live-job/storage observation and full-size SSD resource preflight.

Never fit, copy factors, move a live file, change a source or infer audio quality.
The SSD probe directory holds no matrices. Existing full resource guards remain.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from datetime import datetime, timezone


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def hardware():
    script = r"""
$ErrorActionPreference = 'Stop'
[ordered]@{
    partitions = @(Get-Partition | Where-Object { $_.DriveLetter } | Select-Object DriveLetter,DiskNumber,Size)
    disks = @(Get-PhysicalDisk | Select-Object DeviceId,FriendlyName,MediaType,BusType,Size,HealthStatus)
    volumes = @(Get-Volume | Where-Object { $_.DriveLetter } | Select-Object DriveLetter,FileSystem,Size,SizeRemaining)
    processes = @(Get-Process -Id 65232,441220 -ErrorAction SilentlyContinue | Select-Object Id,StartTime,CPU,WorkingSet64)
    fit_io = @(Get-CimInstance Win32_PerfFormattedData_PerfProc_Process -Filter 'IDProcess = 65232' | Select-Object IDProcess,PercentProcessorTime,IOReadBytesPersec,IOWriteBytesPersec)
} | ConvertTo-Json -Depth 6
"""
    result = subprocess.run(
        ['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', script],
        check=True, capture_output=True, text=True,
        creationflags=subprocess.CREATE_NO_WINDOW)
    return json.loads(result.stdout)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'out', 'probe-dir'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[name] = '2'
    sys.path.insert(0, str(args.workspace / 'tools/python_deps'))
    from waveform_file_real_v1.resources import preflight

    args.out.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, args.out / 'executed_inspection.py')
    report = dict(result='running', observed_utc=datetime.now(timezone.utc).isoformat(),
                  inputs={}, cases=[], no_fit_or_live_file_mutation=True)
    output = args.out / 'report.json'

    def read(path):
        report['inputs'][str(path)] = digest(path)
        return json.loads(path.read_text(encoding='utf-8'))

    def frozen(manifest):
        for path, expected in manifest['source_sha256'].items():
            assert digest(path) == expected, path
        assert digest(manifest['run_spec']) == manifest['run_spec_sha256']

    try:
        manifest = read(args.workspace / 'references/analysis/locked_source_diagnostics_followthrough_v1/manifest.json')
        frozen(manifest)
        report['hardware'] = hardware()
        drive = args.probe_dir.drive.rstrip(':').upper()
        assert drive and drive != 'E', 'Use a separate SSD probe, never the live factor tree'
        partition = next(p for p in report['hardware']['partitions'] if p['DriveLetter'] == drive)
        disk = next(d for d in report['hardware']['disks'] if str(d['DeviceId']) == str(partition['DiskNumber']))
        # PowerShell serializes these enums as numeric values: SSD=4, NVMe=17.
        assert disk['MediaType'] in (4, 'SSD') and disk['HealthStatus'] in (0, 'Healthy'), disk
        assert not args.probe_dir.exists()
        args.probe_dir.mkdir(parents=True)
        report['probe_dir'] = str(args.probe_dir)
        report['probe_contains_no_factor_files'] = True

        prepared_dir = args.workspace / 'references/analysis/locked_source_fit_v1/prepare1'
        prepared = read(prepared_dir / 'report.json')
        proof = read(args.workspace / 'references/analysis/locked_source_fit_v1/prepare_audit1/report.json')
        assert prepared['result'] == 'locked_source_five_prepared' and len(prepared['cases']) == 5
        assert proof['result'] == 'independent_locked_source_preparation_verified' and proof['all_qualified']
        assert proof['producer_sha256'] == digest(prepared_dir / 'report.json')
        unchanged = ('major_phase_panel_arithmetic', 'resident_misc_allowance',
                     'main_phase_array_allowance', 'native_temporary_allowance', 'headroom_guard',
                     'required_available', 'full_factor_file_bytes', 'full_factor_disk_bytes',
                     'disk_output_allowance', 'disk_guard', 'required_available_disk',
                     'graph_transpose_three_owned_panels_counted')
        total = 0
        for row in prepared['cases']:
            path = prepared_dir / row['file']
            assert digest(path) == row['sha256']
            report['inputs'][str(path)] = row['sha256']
            assert row['orders'] == 288
            budget = preflight(args.probe_dir, row['frames'], row['nodes'], 288, 1024)
            assert all(budget[key] == row['resources'][key] for key in unchanged), row['label']
            n, k = 2 * row['nodes'] * 288, min(row['frames'], 2 * row['nodes'] * 288)
            independent = dict(source=8*row['frames']*n, graph=8*(k+n)*k,
                               right=8*n*k, inner=16*k*k)
            assert independent == budget['full_factor_file_bytes']
            assert budget['memory_passed'] and budget['disk_passed']
            total += sum(independent.values())
            report['cases'].append(dict(label=row['label'], resources=budget,
                geometry_and_all_original_reserves_exact=True,
                independent_file_size_arithmetic_exact=True))
        free = shutil.disk_usage(args.probe_dir).free
        assert total == prepared['retained_five_factor_bytes']
        assert free >= total + 2*1024**3
        frozen(manifest)
        report.update(result='locked_source_ssd_storage_preflight_verified',
            all_original_five_factor_bytes=total, original_global_disk_guard_bytes=2*1024**3,
            ssd_available_bytes=free, all_five_reservation_passed=True,
            frozen_source_count=len(manifest['source_sha256']), frozen_sources_unchanged=True,
            source_method_geometry_scales_and_guards_unchanged=True,
            no_fit_command_or_factor_copy_or_process_restart=True,
            no_runtime_C_model_driver_default_or_hearing_change=True,
            no_speedup_measurement_or_terminal_fit_or_audio_qualification=True,
            next_real_fit_not_launched=True)
        print(json.dumps(dict(result=report['result'], full_factor_GiB=total/2**30,
                              ssd_free_GiB=free/2**30, checked_cases=len(report['cases']))))
    except BaseException as error:
        report.update(result='failed', error=repr(error))
        raise
    finally:
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2,
                                     allow_nan=False)+'\n', encoding='utf-8', newline='\n')


if __name__ == '__main__':
    main()

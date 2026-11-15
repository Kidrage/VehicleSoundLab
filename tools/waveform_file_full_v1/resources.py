"""Declared full buffer/disk arithmetic and non-owning process telemetry."""
import os
from pathlib import Path
import shutil
import time
from research_archive_v1 import save
from waveform_structured_v1.resources import ArrayLedger, process_memory
from run_waveform_stream_full_v1 import physical_memory


def preflight(directory, N=12289, M=49, H=288, block=1024):
    n, k = 2*M*H, min(N, 2*M*H)
    band = 8*4096*N
    source_panel, row_panel = 8*N*block, 8*n*block
    graph_panel = 8*(k+n)*block
    phases = dict(source_columns=band+2*source_panel,
        row_whitening=band+4*row_panel,
        source_QR=band+2*source_panel,
        graph_transpose=band+8*k*block+2*row_panel,
        graph_QR=band+2*graph_panel,
        inverse_right=2*row_panel, inverse_inner=2*8*(2*k)*block,
        diagonal_and_update=2*8*block*block+8*(N+n+k)*4)
    resident_misc = 128*1024**2
    main = max(phases.values())+resident_misc
    reserve, guard = 3*1024**3//2, 3*1024**3
    files = dict(source=8*N*n, graph=8*(k+n)*k, right=8*n*k, inner=16*k*k)
    disk_allowance = disk_guard = 1024**3
    memory = physical_memory()
    available_disk = shutil.disk_usage(directory).free
    return dict(**memory, available_disk_bytes=available_disk,
        major_phase_panel_arithmetic=phases, resident_misc_allowance=resident_misc,
        main_phase_array_allowance=main, native_temporary_allowance=reserve, headroom_guard=guard,
        required_available=main+reserve+guard,
        memory_passed=min(memory['available_physical_bytes'], memory['available_commit_bytes']) >= main+reserve+guard,
        full_factor_file_bytes=files, full_factor_disk_bytes=sum(files.values()),
        disk_output_allowance=disk_allowance, disk_guard=disk_guard,
        required_available_disk=sum(files.values())+disk_allowance+disk_guard,
        disk_passed=available_disk >= sum(files.values())+disk_allowance+disk_guard,
        conditional_arithmetic_NOT_actual_peak_proof=True)


class Telemetry(ArrayLedger):
    def __init__(self, directory):
        super().__init__()
        self.directory = Path(directory)
        self.started = time.monotonic()
        self.last_print = -100.
        self.active_file = None
        self.counts = {}

    def add(self, name, value):
        if name.startswith('file.read.'):
            self.active_file = name.removeprefix('file.read.')
        return super().add(name, value)

    def snapshot(self, phase):
        super().snapshot(phase)
        self.counts[phase] = self.counts.get(phase, 0)+1
        elapsed = time.monotonic()-self.started
        memory = physical_memory()
        if memory['available_physical_bytes'] < 1024**3:
            raise MemoryError('Full file checkpoint below original1GiB physical guard')
        if elapsed-self.last_print >= 10 or phase.startswith('fullPipeline.'):
            value = dict(pid=os.getpid(), status='running', phase=phase, active_file=self.active_file,
                phase_counts=self.counts, elapsed_seconds=elapsed, **process_memory(), **memory)
            self.progress(value)
            print('FILE_FULL', phase, self.active_file, round(elapsed, 2),
                  'WS', value['working_set_bytes'], 'FREE', memory['available_physical_bytes'], flush=True)
            self.last_print = elapsed

    def progress(self, value):
        temp = self.directory/'progress.tmp.json'
        save(temp, value)
        temp.replace(self.directory/'progress.json')

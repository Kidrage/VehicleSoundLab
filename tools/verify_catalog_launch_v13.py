"""Owned workbench server launches and reuses an actual independent V13 window."""
import argparse
import ctypes as C
from pathlib import Path
import shutil
import subprocess
import threading
import time
from unittest.mock import patch

from PIL import ImageGrab

from research_archive_v1 import load, save
from sound_designer.controller import Controller
from sound_designer.server import create_server
from vehicle_controller.native import Bridge


def windows(pid):
    result = []
    user = C.windll.user32
    callback_type = C.WINFUNCTYPE(C.c_bool, C.c_void_p, C.c_ssize_t)
    @callback_type
    def visit(hwnd, unused):
        owner = C.c_ulong()
        user.GetWindowThreadProcessId(C.c_void_p(hwnd), C.byref(owner))
        if owner.value == pid and user.IsWindowVisible(C.c_void_p(hwnd)):
            title = C.create_unicode_buffer(256)
            user.GetWindowTextW(C.c_void_p(hwnd), title, 256)
            if title.value == 'VEHICLE SOUND · 驾驶与声源控制 V13':
                result.append(hwnd)
        return True
    user.EnumWindows(visit, 0)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    repo = Path(__file__).resolve().parents[1]
    shutil.copy2(__file__,out/'executed_verification.py')
    shutil.copy2(repo/'tools/verify_catalog_launch_v13.cjs',out/'executed_browser.cjs')
    owned = []
    class TrackedController(Controller):
        def __init__(self, *arguments, **keywords):
            super().__init__(*arguments, **keywords)
            owned.append(self)
    with patch('sound_designer.server.Controller',TrackedController):
        server = create_server(repo,out/'workspace/projects',0)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    report = dict(result='running',goal_complete=False,timbre_accepted=False,persistent_service_restarted=False)
    try:
        node = Path('C:/Users/mlslabs-06/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe')
        result = subprocess.run([str(node),str(out/'executed_browser.cjs'),str(node.parents[1]/'node_modules'),
            f'http://127.0.0.1:{server.server_address[1]}/',str(out/'browser')],
            capture_output=True,timeout=60,creationflags=0x08000000)
        (out/'stdout.log').write_bytes(result.stdout)
        (out/'stderr.log').write_bytes(result.stderr)
        assert result.returncode == 0, result.stderr.decode(errors='replace')
        checked = load(out/'browser/report.json')
        assert checked['result'] == 'passed'
        assert len(owned) == 1 and owned[0].process.poll() is None
        controller = owned[0]
        deadline = time.monotonic()+15
        while not controller.ready.is_file():
            assert controller.process.poll() is None and time.monotonic() < deadline
            time.sleep(.05)
        ready = load(controller.ready)
        assert ready['pid'] == checked['first']['pid'] == controller.process.pid
        assert ready['ui_revision'] == 13 and ready['preset_schema'] == 8 and ready['take_schema'] == 9
        assert ready['source_only'] and not ready['listening'] and ready['abi'] == 11
        assert ready['catalog_assets_sha256'] == Bridge(repo).catalog_assets_sha256
        handles = windows(controller.process.pid)
        assert len(handles) == 1
        ImageGrab.grab(window=handles[0]).save(out/'independent-window.png')
        report.update(result='passed',browser=checked,ready=ready,actual_window_seen=True,
            no_audio_autoplay=True,duplicate_launch_reused=True)
    except Exception as error:
        report.update(result='failed',error=repr(error))
        raise
    finally:
        for controller in owned:
            if controller.process is not None and controller.process.poll() is None:
                for hwnd in windows(controller.process.pid):
                    C.windll.user32.PostMessageW(C.c_void_p(hwnd),0x0010,0,0)
                try:
                    controller.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    controller.process.terminate()
                    controller.process.wait(timeout=5)
                    report['own_process_forced_close'] = True
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        report['own_window_closed'] = all(c.process is None or c.process.poll() is not None for c in owned)
        report['own_service_closed'] = not thread.is_alive()
        save(out/'report.json',report)


if __name__ == '__main__':
    main()

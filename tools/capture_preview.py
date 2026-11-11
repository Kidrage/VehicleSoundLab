"""Capture only this project's own diagnostic window, then close that process."""
from pathlib import Path
import argparse
import ctypes
from ctypes import wintypes
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/python_deps'))
from PIL import Image
parser=argparse.ArgumentParser()
parser.add_argument('--build-dir',type=Path,default=ROOT/'build-v07')
parser.add_argument('--out',type=Path,default=ROOT/'renders/v0.7.0/ui_native_preview.png')
args=parser.parse_args()
exe=args.build_dir/'Release/VehicleSoundLab.exe'
target=args.out
capture=ROOT/'renders/ui_live_preview.bmp'
before=capture.stat().st_mtime_ns if capture.exists() else 0
startup=subprocess.STARTUPINFO();startup.dwFlags|=subprocess.STARTF_USESHOWWINDOW
startup.wShowWindow=4  # Visible test window without activation; no audio starts.
child=subprocess.Popen([str(exe),'--preview-capture'],cwd=ROOT,startupinfo=startup)
user32=ctypes.windll.user32
callback_type=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
@callback_type
def close_owned(hwnd,param):
    pid=wintypes.DWORD();user32.GetWindowThreadProcessId(hwnd,ctypes.byref(pid))
    if pid.value==child.pid:user32.PostMessageW(hwnd,0x10,0,0)
    return True
try:
    for _ in range(50):
        if child.poll() is not None:raise RuntimeError('Preview process exited before capture')
        if capture.exists() and capture.stat().st_mtime_ns>before:
            with Image.open(capture) as im:im.save(target)
            break
        time.sleep(.2)
    else:raise RuntimeError('Preview capture timed out')
finally:
    user32.EnumWindows(close_owned,0)
    try:child.wait(timeout=5)
    except subprocess.TimeoutExpired:child.terminate();child.wait(timeout=5)
print(target)

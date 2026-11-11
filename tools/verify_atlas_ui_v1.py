"""Exercise only the new project's own muted Windows UI through native messages."""
import argparse
import ctypes as C
from ctypes import wintypes as W
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True)
parser.add_argument('--out',type=Path,required=True)
args=parser.parse_args()
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
from PIL import Image
repo=Path(__file__).resolve().parents[1]
args.out.mkdir(parents=True,exist_ok=False)
u=C.windll.user32;g=C.windll.gdi32
u.SetProcessDPIAware()
u.SendMessageW.argtypes=[W.HWND,W.UINT,W.WPARAM,W.LPARAM];u.SendMessageW.restype=C.c_ssize_t
u.GetDlgItem.argtypes=[W.HWND,C.c_int];u.GetDlgItem.restype=W.HWND
u.GetWindowThreadProcessId.argtypes=[W.HWND,C.POINTER(W.DWORD)]
u.GetWindowTextW.argtypes=[W.HWND,W.LPWSTR,C.c_int]
u.GetClassNameW.argtypes=[W.HWND,W.LPWSTR,C.c_int]
u.GetWindowRect.argtypes=[W.HWND,C.POINTER(W.RECT)]
u.PrintWindow.argtypes=[W.HWND,W.HDC,W.UINT]
u.RedrawWindow.argtypes=[W.HWND,C.c_void_p,W.HRGN,W.UINT]
u.UpdateWindow.argtypes=[W.HWND]
u.GetDC.argtypes=[W.HWND];u.GetDC.restype=W.HDC
u.ReleaseDC.argtypes=[W.HWND,W.HDC]
u.IsWindowEnabled.argtypes=[W.HWND]
g.CreateCompatibleDC.argtypes=[W.HDC];g.CreateCompatibleDC.restype=W.HDC
g.CreateCompatibleBitmap.argtypes=[W.HDC,C.c_int,C.c_int];g.CreateCompatibleBitmap.restype=W.HBITMAP
g.SelectObject.argtypes=[W.HDC,W.HGDIOBJ];g.SelectObject.restype=W.HGDIOBJ
g.DeleteObject.argtypes=[W.HGDIOBJ];g.DeleteDC.argtypes=[W.HDC]
class Header(C.Structure):
    _fields_=[('size',W.DWORD),('width',W.LONG),('height',W.LONG),('planes',W.WORD),('bits',W.WORD),
              ('compression',W.DWORD),('image_size',W.DWORD),('x',W.LONG),('y',W.LONG),('used',W.DWORD),('important',W.DWORD)]
g.GetDIBits.argtypes=[W.HDC,W.HBITMAP,W.UINT,W.UINT,C.c_void_p,C.POINTER(Header),W.UINT]

def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

exe=repo/'handoff-build/bin/Release/VslAtlasMonitor.exe'
startup=subprocess.STARTUPINFO();startup.dwFlags|=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=4
child=subprocess.Popen([str(exe),'--muted'],cwd=repo,startupinfo=startup)
window=None
callback=C.WINFUNCTYPE(W.BOOL,W.HWND,W.LPARAM)
@callback
def visit(hwnd,param):
    global window
    pid=W.DWORD();u.GetWindowThreadProcessId(hwnd,C.byref(pid))
    klass=C.create_unicode_buffer(128);u.GetClassNameW(hwnd,klass,len(klass))
    if pid.value==child.pid and klass.value=='VslAtlasMonitor':window=hwnd
    return True
def text(hwnd):
    buf=C.create_unicode_buffer(512);u.GetWindowTextW(hwnd,buf,len(buf));return buf.value
def wait(predicate,seconds=6):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        if predicate():return
        if child.poll() is not None:raise RuntimeError('UI exited early: '+str(child.returncode))
        time.sleep(.02)
    raise AssertionError('UI condition timed out')
def control(id):
    handle=u.GetDlgItem(window,id);assert handle,id;return handle
def select(id,value):
    assert u.SendMessageW(control(id),0x14e,value,0)==value
    u.SendMessageW(window,0x111,id|(1<<16),control(id))
def slider(id,value):
    u.SendMessageW(control(id),0x405,1,value)
    u.SendMessageW(window,0x114,5,control(id))
def click(id):u.SendMessageW(control(id),0xf5,0,0)
def screenshot(name):
    assert u.RedrawWindow(window,None,None,0x185)  # Synchronous parent+child repaint.
    u.UpdateWindow(window)
    time.sleep(.12)
    rect=W.RECT();assert u.GetWindowRect(window,C.byref(rect));w,h=rect.right-rect.left,rect.bottom-rect.top
    dc=u.GetDC(window);memory=g.CreateCompatibleDC(dc);bitmap=g.CreateCompatibleBitmap(dc,w,h);old=g.SelectObject(memory,bitmap)
    try:
        assert u.PrintWindow(window,memory,0)
        info=Header(C.sizeof(Header),w,-h,1,32,0,w*h*4,0,0,0,0)
        pixels=C.create_string_buffer(w*h*4)
        assert g.GetDIBits(memory,bitmap,0,h,pixels,C.byref(info),0)==h
        Image.frombytes('RGB',(w,h),pixels.raw,'raw','BGRX').save(args.out/name)
    finally:g.SelectObject(memory,old);g.DeleteObject(bitmap);g.DeleteDC(memory);u.ReleaseDC(window,dc)
    return [w,h]

try:
    wait(lambda:u.EnumWindows(visit,0) and window is not None)
    wait(lambda:bool(u.GetDlgItem(window,61)))
    assert '已停止' in text(control(61))
    assert '0%' in text(control(76))
    geometry=screenshot('initial.png')
    select(41,1)
    assert not u.IsWindowEnabled(control(20)) and not u.IsWindowEnabled(control(21)) and u.IsWindowEnabled(control(22))
    assert not u.IsWindowEnabled(control(42))
    slider(22,4000);slider(23,-12)
    assert '4000' in text(control(72)) and '-12' in text(control(73))
    before=[text(control(70+i)) for i in (0,1,2,3)]
    slider(26,50)
    assert '50%' in text(control(76)) and before==[text(control(70+i)) for i in (0,1,2,3)]
    click(30);assert u.SendMessageW(control(30),0xf0,0,0)==1
    assert u.IsWindowEnabled(control(24)) and u.IsWindowEnabled(control(25))
    slider(24,60);slider(25,35)
    assert before==[text(control(70+i)) for i in (0,1,2,3)]
    select(42,1)
    click(10);click(12)
    wait(lambda:'监听中' in text(control(61)))
    wait(lambda:'4000 RPM' in text(control(60)))
    slider(22,7600)
    wait(lambda:'7600 RPM' in text(control(60)))
    select(40,1)
    wait(lambda:'已停止' in text(control(61)))
    assert '7600' in text(control(72)) and '-12' in text(control(73))
    assert '60%' in text(control(74)) and '35%' in text(control(75))
    assert '50%' in text(control(76))
    click(10);wait(lambda:'监听中' in text(control(61)))
    wait(lambda:'7600 RPM' in text(control(60)))
    time.sleep(.4)
    screenshot('cabin_live.png')
    click(11);wait(lambda:'已停止' in text(control(61)))
    select(40,0);select(41,0)
    assert u.IsWindowEnabled(control(20)) and not u.IsWindowEnabled(control(22))
    assert u.IsWindowEnabled(control(42))
    # Visible controls must fit the actual native window.
    outer=W.RECT();u.GetWindowRect(window,C.byref(outer))
    for id in [10,11,12,20,21,22,23,24,25,26,30,31,40,41,42,60,61,76]:
        r=W.RECT();u.GetWindowRect(control(id),C.byref(r))
        assert r.left>=outer.left and r.right<=outer.right and r.bottom<=outer.bottom,id
    report=dict(result='pass',muted=True,no_autoplay=True,bench_rpm_live=True,transport=True,
        context_switch_stops_playback=True,unrelated_controls_preserved=True,mode_enablement=True,
        residual_control=True,window_geometry=geometry,binary_sha256=sha(exe),verifier_sha256=sha(__file__))
    (args.out/'verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report))
finally:
    if window:u.SendMessageW(window,0x10,0,0)
    try:child.wait(timeout=8)
    except subprocess.TimeoutExpired:child.terminate();child.wait(timeout=5)

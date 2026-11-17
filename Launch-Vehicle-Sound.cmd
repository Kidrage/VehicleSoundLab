@echo off
setlocal
set "VSL_APP_PYTHONW=C:\Users\mlslabs-06\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\pythonw.exe"
if not exist "%VSL_APP_PYTHONW%" goto console
start "" "%VSL_APP_PYTHONW%" "%~dp0tools\run_vehicle_controller.py" %*
exit /b
:console
call "%~dp0Launch-Vehicle-Controller.cmd" %*

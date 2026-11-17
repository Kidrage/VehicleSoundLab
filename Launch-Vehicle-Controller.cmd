@echo off
setlocal
set "VSL_CONTROLLER_PYTHON=C:\Users\mlslabs-06\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if not exist "%VSL_CONTROLLER_PYTHON%" set "VSL_CONTROLLER_PYTHON=python"
"%VSL_CONTROLLER_PYTHON%" "%~dp0tools\run_vehicle_controller.py" %*

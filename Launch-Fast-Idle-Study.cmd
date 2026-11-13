@echo off
cd /d "%~dp0"
if exist "build-idle-microtexture-v1\Release\VslFastIdleMonitor.exe" (
  start "" "build-idle-microtexture-v1\Release\VslFastIdleMonitor.exe" "%~dp0."
  exit /b 0
)
echo Please run Build-Fast-Idle-Study.ps1 first.
pause
exit /b 1

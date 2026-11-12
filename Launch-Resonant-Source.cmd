@echo off
cd /d "%~dp0"
if exist "build-resonant-monitor-v1\bin\Release\VslResonantMonitor.exe" (
  start "" "build-resonant-monitor-v1\bin\Release\VslResonantMonitor.exe"
  exit /b 0
)
if exist "handoff-build\bin\Release\VslResonantMonitor.exe" (
  start "" "handoff-build\bin\Release\VslResonantMonitor.exe"
  exit /b 0
)
echo Please run Build-System.ps1 first.
pause
exit /b 1

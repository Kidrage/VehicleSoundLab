@echo off
cd /d "%~dp0"
if exist "build-layer-monitor-v1\bin\Release\VslAtlasMonitor.exe" (
  start "" "build-layer-monitor-v1\bin\Release\VslAtlasMonitor.exe" --fine-idle-study
  exit /b 0
)
echo Please run Build-Layer-Monitor-Study.ps1 first.
pause
exit /b 1

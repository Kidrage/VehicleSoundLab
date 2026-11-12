@echo off
cd /d "%~dp0"
if exist "build-stereo-drive-v1\bin\Release\VslAtlasMonitor.exe" (
  start "" "build-stereo-drive-v1\bin\Release\VslAtlasMonitor.exe" --stereo-resonant-study
  exit /b 0
)
if exist "handoff-build\bin\Release\VslAtlasMonitor.exe" (
  start "" "handoff-build\bin\Release\VslAtlasMonitor.exe" --stereo-resonant-study
  exit /b 0
)
echo Please run Build-System.ps1 first.
pause
exit /b 1

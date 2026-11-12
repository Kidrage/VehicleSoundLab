@echo off
cd /d "%~dp0"
if exist "build-drive-resonance-v1\bin\Release\VslAtlasMonitor.exe" (
  start "" "build-drive-resonance-v1\bin\Release\VslAtlasMonitor.exe" --resonant-study
  exit /b 0
)
if exist "handoff-build\bin\Release\VslAtlasMonitor.exe" (
  start "" "handoff-build\bin\Release\VslAtlasMonitor.exe" --resonant-study
  exit /b 0
)
echo Please run Build-System.ps1 first.
pause
exit /b 1

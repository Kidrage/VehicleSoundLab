@echo off
cd /d "%~dp0"
if not exist "build-startup-detail-host-v1\bin\Release\VslAtlasMonitor.exe" (
  echo Build with cmake -S handoff -B build-startup-detail-host-v1 -A x64
  echo Then cmake --build build-startup-detail-host-v1 --config Release
  exit /b 2
)
start "" "build-startup-detail-host-v1\bin\Release\VslAtlasMonitor.exe" --startup-detail-study

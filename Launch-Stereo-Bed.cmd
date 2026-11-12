@echo off
cd /d "%~dp0"
if not exist "build-stereo-bed-v1\bin\Release\VslAtlasMonitor.exe" (
  echo Build with cmake -S handoff -B build-stereo-bed-v1 -A x64
  echo Then cmake --build build-stereo-bed-v1 --config Release
  exit /b 2
)
start "" "build-stereo-bed-v1\bin\Release\VslAtlasMonitor.exe" --stereo-bed

@echo off
cd /d "%~dp0"
if not exist "build-catch-drive-v1\bin\Release\VslAtlasMonitor.exe" (
  echo Build with cmake -S handoff -B build-catch-drive-v1 -A x64
  echo Then cmake --build build-catch-drive-v1 --config Release
  exit /b 2
)
start "" "build-catch-drive-v1\bin\Release\VslAtlasMonitor.exe" --catch-study

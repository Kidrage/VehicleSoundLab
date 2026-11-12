@echo off
cd /d "%~dp0"
if not exist "build-phase-texture-c-v1\bin\Release\VslSceneMonitor.exe" (
  echo Build with cmake -S handoff -B build-phase-texture-c-v1 -A x64
  echo Then cmake --build build-phase-texture-c-v1 --config Release
  exit /b 2
)
start "" "build-phase-texture-c-v1\bin\Release\VslSceneMonitor.exe" --phase-texture

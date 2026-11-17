@echo off
cd /d "%~dp0"
if not exist "handoff-build\bin\Release\VslAtlasMonitor.exe" (
  echo Please run Build-System.ps1 first.
  exit /b 2
)
start "" "handoff-build\bin\Release\VslAtlasMonitor.exe"

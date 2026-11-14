@echo off
cd /d "%~dp0"
if exist "build-bench-load-v1\bin\Release\VslAtlasMonitor.exe" (
  start "" "build-bench-load-v1\bin\Release\VslAtlasMonitor.exe" --catalog
  exit /b 0
)
echo Please run Build-Voice-Catalog.ps1 first.
pause
exit /b 1

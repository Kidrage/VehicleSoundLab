@echo off
cd /d "%~dp0"
if exist "build-catalog-bridge-v1\bin\Release\VslAtlasMonitor.exe" (
  start "" "build-catalog-bridge-v1\bin\Release\VslAtlasMonitor.exe" --catalog
  exit /b 0
)
echo Please run Build-Voice-Catalog.ps1 first.
pause
exit /b 1

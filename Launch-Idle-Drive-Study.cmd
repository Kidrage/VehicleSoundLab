@echo off
cd /d "%~dp0"
if exist "build-idle-drive-v1\bin\Release\VslAtlasMonitor.exe" (
  start "" "build-idle-drive-v1\bin\Release\VslAtlasMonitor.exe" --idle-study
  exit /b 0
)
echo Please run Build-Idle-Drive-Study.ps1 first.
pause
exit /b 1

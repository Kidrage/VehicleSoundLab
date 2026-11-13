@echo off
cd /d "%~dp0"
if exist "build-fine-idle-drive-v1\bin\Release\VslAtlasMonitor.exe" (
  start "" "build-fine-idle-drive-v1\bin\Release\VslAtlasMonitor.exe" --fine-idle-study
  exit /b 0
)
echo Please run Build-Fine-Idle-Drive-Study.ps1 first.
pause
exit /b 1

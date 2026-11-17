@echo off
setlocal
cd /d "%~dp0"
if /i "%~1"=="rebuilt" goto rebuilt
if not exist "%~dp0handoff\bin\VslSystem.exe" goto rebuilt
start "Vehicle Sound Lab" "%~dp0handoff\bin\VslSystem.exe"
exit /b
:rebuilt
if not exist "%~dp0handoff-build\bin\Release\VslSystem.exe" goto missing
start "Vehicle Sound Lab" "%~dp0handoff-build\bin\Release\VslSystem.exe" --rebuilt
exit /b
:missing
echo Run Build-System.ps1 first.
pause
exit /b 1

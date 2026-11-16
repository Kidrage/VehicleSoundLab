param([string]$Workspace = 'E:/VehicleSoundLab', [int]$Port = 8791)
$ErrorActionPreference = 'Stop'
$vslPython = Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
if (!(Test-Path -LiteralPath $vslPython)) { $vslPython = (Get-Command python -ErrorAction Stop).Source }
$vslUrl = "http://127.0.0.1:$Port"
try {
    $vslStatus = Invoke-RestMethod "$vslUrl/api/config" -TimeoutSec 2
    if ($vslStatus.schema -eq 'vsl.sound-designer-server/1') { Start-Process $vslUrl; exit 0 }
} catch {}
$vslExporter = Join-Path $PSScriptRoot 'build-sound-dna-export-v1/bin/Release/sound_dna_export.exe'
if (!(Test-Path -LiteralPath $vslExporter)) { throw 'Run Build-Sound-Designer.ps1 first.' }
$vslScript = Join-Path $PSScriptRoot 'tools/run_sound_designer.py'
$vslLog = Join-Path $Workspace 'designs'
New-Item -ItemType Directory -Path $vslLog -Force | Out-Null
$vslProcess = Start-Process -FilePath $vslPython -ArgumentList @('"' + $vslScript + '"', '--workspace', '"' + $Workspace + '"', '--port', $Port, '--no-browser') -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $vslLog 'server.log') -RedirectStandardError (Join-Path $vslLog 'server-error.log')
for ($vslAttempt = 0; $vslAttempt -lt 30; $vslAttempt++) {
    Start-Sleep -Milliseconds 250
    if ($vslProcess.HasExited) { throw "Server exited. Read $vslLog/server-error.log" }
    try {
        $vslStatus = Invoke-RestMethod "$vslUrl/api/config" -TimeoutSec 1
        if ($vslStatus.schema -eq 'vsl.sound-designer-server/1') { Start-Process $vslUrl; exit 0 }
    } catch {}
}
throw "Server did not become ready. Read $vslLog/server-error.log"

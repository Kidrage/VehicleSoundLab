param(
    [Parameter(Mandatory=$true)][string]$Workspace,
    [Parameter(Mandatory=$true)][string]$Out
)
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$claim = 'D:\VehicleSoundLab-Work\source_fit_storage_v1\c1_22k_declared_v1\claims\3cfbdb688cd83cba917e7071e5de5f7b73b1daa0872d39ccf6b3ede1fe50092d'
$python = 'C:\Users\mlslabs-06\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$study = Join-Path $Workspace 'references\analysis\c1_native_diagnostics_v1'
$sourceId = 277576
$sourceCreation = [datetimeoffset]'2026-11-16T10:24:04.676262+08:00'
if (Test-Path -LiteralPath $Out) { throw 'New followthrough output required; never restart an existing attempt' }
New-Item -ItemType Directory -Path $Out | Out-Null
Copy-Item -LiteralPath $PSCommandPath -Destination (Join-Path $Out 'executed_followthrough.ps1')
$record = [ordered]@{
    result='running'; state='checking_qualified_knowns'; pid=$PID; source_pid=$sourceId
    source_creation=$sourceCreation.ToString('o'); claim=$claim; stages=@()
    no_fit_restart_or_runtime_or_hearing_change=$true
}
function Save-Record {
    $json = $record | ConvertTo-Json -Depth 12
    [IO.File]::WriteAllText((Join-Path $Out 'report.json'), $json+[Environment]::NewLine, [Text.UTF8Encoding]::new($false))
}
Save-Record
try {
    $knownPath = Join-Path $study 'known2\report.json'
    $auditPath = Join-Path $study 'known_declared_audit2\report.json'
    $known = Get-Content -LiteralPath $knownPath -Raw | ConvertFrom-Json
    $audit = Get-Content -LiteralPath $auditPath -Raw | ConvertFrom-Json
    $knownHash = (Get-FileHash -LiteralPath $knownPath -Algorithm SHA256).Hash.ToLowerInvariant()
    if (-not $known.all_known_qualified -or -not $audit.verification_passed -or
        -not $audit.all_operator_and_declared_statistics_verified -or -not $audit.all_known_qualified -or
        $audit.producer_sha256 -ne $knownHash -or
        $audit.schema -ne 'vsl.c1-native-declared-centering-audit/1') { throw 'Complete new C1 known/declared audit required' }
    $record.known_sha256 = $knownHash
    $record.known_audit_sha256 = (Get-FileHash -LiteralPath $auditPath -Algorithm SHA256).Hash.ToLowerInvariant()
    $sourceProcess = Get-CimInstance Win32_Process -Filter "ProcessId=$sourceId"
    if ($null -eq $sourceProcess -or
        [math]::Abs((([datetimeoffset]$sourceProcess.CreationDate)-$sourceCreation).TotalMilliseconds) -gt 1 -or
        $sourceProcess.CommandLine -notlike '*tools/run_c1_registered_source_v1.py --workspace E:\VehicleSoundLab*') {
        throw 'Original live process/creation/command identity required at coordinator start'
    }
    $record.state = 'waiting_for_same_registered_process'
    Save-Record
    $originalHandle = Get-Process -Id $sourceId
    while (-not $originalHandle.WaitForExit(30000)) { }
    $receiptPath = Join-Path $claim 'execution_result.json'
    $receipt = Get-Content -LiteralPath $receiptPath -Raw | ConvertFrom-Json
    $mathPath = Join-Path $claim 'run1_audit\report.json'
    $math = Get-Content -LiteralPath $mathPath -Raw | ConvertFrom-Json
    if ($receipt.result -ne 'c1_registered_single_run_complete' -or $receipt.pid -ne $sourceId -or
        -not $receipt.solver_qualified -or -not $math.verification_passed -or
        -not $math.case.solver_qualified -or
        $receipt.audit_report_sha256 -ne (Get-FileHash -LiteralPath $mathPath -Algorithm SHA256).Hash.ToLowerInvariant()) {
        throw 'Same registered source failed or lacks complete independent mathematical qualification; no retry'
    }
    $record.source_receipt_sha256 = (Get-FileHash -LiteralPath $receiptPath -Algorithm SHA256).Hash.ToLowerInvariant()
    $record.state = 'native_real'
    Save-Record
    & $python (Join-Path $PSScriptRoot 'run_c1_native_diagnostics_v1.py') --workspace $Workspace --out (Join-Path $study 'real1') --mode real --known-study (Join-Path $study 'known2') --known-audit (Join-Path $study 'known_declared_audit2')
    if ($LASTEXITCODE -ne 0) { throw "New native diagnostic exited $LASTEXITCODE; outputs retained, no retry" }
    $record.stages += 'real1'
    $record.state = 'independent_native_audit'
    Save-Record
    & $python (Join-Path $PSScriptRoot 'audit_c1_native_declared_v1.py') --workspace $Workspace --study (Join-Path $study 'real1') --out (Join-Path $study 'real_declared_audit1')
    if ($LASTEXITCODE -ne 0) { throw "Independent native audit exited $LASTEXITCODE; outputs retained, no retry" }
    $record.stages += 'real_declared_audit1'
    $record.result = 'c1_native_followthrough_complete'
    $record.state = 'terminal'
    $record.eligible_for_later_source_statistics = $false
    Save-Record
} catch {
    $record.result = 'failed'
    $record.state = 'terminal'
    $record.error = $_.Exception.Message
    Save-Record
    throw
}

param([Parameter(Mandatory=$true)][string]$ManifestPath)
$ErrorActionPreference = 'Stop'
$manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
$reportPath = Join-Path $manifest.out 'report.json'
if (Test-Path -LiteralPath $reportPath) { throw 'Refuse to overwrite an existing followthrough report' }
$report = [ordered]@{
    schema = 'vsl.locked_source_diagnostic_followthrough/1'
    result = 'starting'
    pid = $PID
    started_utc = [DateTime]::UtcNow.ToString('o')
    source_pid = $manifest.source_pid
    source_start_utc_ticks = $manifest.source_start_utc_ticks
    manifest_sha256 = (Get-FileHash -LiteralPath $ManifestPath -Algorithm SHA256).Hash.ToLowerInvariant()
    no_fit_commands = $true
    no_automatic_later_fits = $true
    no_C_or_default_or_hearing_or_sustained_promotion = $true
    stages = @()
}
function Save-Report {
    $text = $report | ConvertTo-Json -Depth 16
    [System.IO.File]::WriteAllText($reportPath, ($text -replace "`r`n", "`n") + "`n", [System.Text.UTF8Encoding]::new($false))
}
function Assert-Frozen {
    foreach ($binding in $manifest.source_sha256.PSObject.Properties) {
        $actual = (Get-FileHash -LiteralPath $binding.Name -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($actual -ne $binding.Value) { throw ('Frozen source changed: ' + $binding.Name) }
    }
    if ((Get-FileHash -LiteralPath $manifest.run_spec -Algorithm SHA256).Hash.ToLowerInvariant() -ne $manifest.run_spec_sha256) {
        throw 'The original immutable run specification changed'
    }
}
try {
    if ($manifest.schema -ne 'vsl.locked_source_diagnostic_followthrough_spec/1') { throw 'Unknown launch manifest' }
    foreach ($stage in $manifest.stages) {
        if (Test-Path -LiteralPath $stage.out) { throw ('Stage already exists; no retry or overwrite: ' + $stage.out) }
    }
    Assert-Frozen
    $spec = Get-Content -LiteralPath $manifest.run_spec -Raw | ConvertFrom-Json
    if ($spec.schema -ne 'vsl.locked_source_real_spec/1' -or $spec.pid -ne $manifest.source_pid -or
        @($spec.declared_cases).Count -ne 1 -or $spec.declared_cases[0] -ne $manifest.label -or
        !$spec.only_one_finite_case -or $manifest.label -eq 'F3 Fifth First Early') { throw 'Wrong source run identity' }
    Set-Location -LiteralPath $manifest.repo
    $fitProcess = Get-Process -Id $manifest.source_pid -ErrorAction SilentlyContinue
    if ($null -ne $fitProcess) {
        $null = $fitProcess.Handle
        if ($fitProcess.StartTime.ToUniversalTime().Ticks.ToString() -ne $manifest.source_start_utc_ticks) {
            throw 'The PID now identifies a different process'
        }
        $report.result = 'waiting_same_live_fit'
        $report.confirmed_live_utc = [DateTime]::UtcNow.ToString('o')
        Save-Report
        Write-Output ('WAITING_SAME_FIT ' + $fitProcess.Id + ' ' + $manifest.label)
        $lastObservation = [DateTime]::UtcNow
        while (!$fitProcess.WaitForExit(10000)) {
            if (([DateTime]::UtcNow - $lastObservation).TotalSeconds -ge 60) {
                $fitProcess.Refresh()
                $report.confirmed_live_utc = [DateTime]::UtcNow.ToString('o')
                $report.source_CPU_seconds = $fitProcess.CPU
                $report.source_working_set_bytes = $fitProcess.WorkingSet64
                Save-Report
                $lastObservation = [DateTime]::UtcNow
                Write-Output ('SAME_FIT_LIVE ' + $manifest.source_pid + ' CPU ' + $report.source_CPU_seconds)
            }
        }
        $report.source_process_exit_code = $fitProcess.ExitCode
        if ($fitProcess.ExitCode -ne 0) { throw ('Source fit exited unsuccessfully: ' + $fitProcess.ExitCode) }
        $fitProcess.Dispose()
    }
    Assert-Frozen
    $terminal = Get-Content -LiteralPath $manifest.source_report -Raw | ConvertFrom-Json
    $proof = Get-Content -LiteralPath $manifest.math_audit -Raw | ConvertFrom-Json
    if ($terminal.result -ne 'locked_source_one_real_measured' -or !$terminal.verification_passed -or
        @($terminal.cases).Count -ne 1 -or $terminal.cases[0].label -ne $manifest.label -or
        $proof.result -ne 'independent_locked_source_real_verified' -or !$proof.verification_passed -or
        !$proof.case.verification_passed) { throw 'No terminal independently verified single changed-source case' }
    if ((Get-FileHash -LiteralPath $manifest.math_audit -Algorithm SHA256).Hash.ToLowerInvariant() -ne $terminal.cases[0].audit_report_sha256) {
        throw 'Terminal run does not bind this mathematical audit'
    }
    if ((Get-FileHash -LiteralPath (Join-Path $manifest.case 'report.json') -Algorithm SHA256).Hash.ToLowerInvariant() -ne $terminal.cases[0].case_report_sha256) {
        throw 'Terminal run does not bind this case report'
    }
    $report.result = 'terminal_math_verified_diagnosing'
    $report.math_audit_sha256 = (Get-FileHash -LiteralPath $manifest.math_audit -Algorithm SHA256).Hash.ToLowerInvariant()
    $report.solver_qualified = $proof.case.solver_qualified
    $report.source_fidelity_qualified = $proof.case.fidelity_qualified
    Save-Report
    foreach ($stage in $manifest.stages) {
        Assert-Frozen
        if (Test-Path -LiteralPath $stage.out) { throw ('Stage appeared while waiting; no overwrite: ' + $stage.out) }
        $stdout = Join-Path $manifest.out ($stage.name + '.stdout.log')
        $stderr = Join-Path $manifest.out ($stage.name + '.stderr.log')
        $stageRecord = [ordered]@{ name=$stage.name; result='running'; started_utc=[DateTime]::UtcNow.ToString('o'); out=$stage.out }
        $report.stages += $stageRecord
        Save-Report
        Write-Output ('DIAGNOSTIC_STAGE_START ' + $stage.name)
        $nativeArguments = @($stage.script) + @($stage.arguments)
        $ErrorActionPreference = 'Continue'
        & $manifest.python @nativeArguments 1> $stdout 2> $stderr
        $stageExit = $LASTEXITCODE
        $ErrorActionPreference = 'Stop'
        $stageRecord.exit_code = $stageExit
        $stageRecord.finished_utc = [DateTime]::UtcNow.ToString('o')
        if ($stageExit -ne 0) {
            $stageRecord.result = 'failed'
            Save-Report
            throw ('Diagnostic stage failed; preserve its outputs: ' + $stage.name + ' exit ' + $stageExit)
        }
        $stageReport = Join-Path $stage.out 'report.json'
        $stageResult = Get-Content -LiteralPath $stageReport -Raw | ConvertFrom-Json
        if ($stageResult.result -ne $stage.expected_result) { throw ('Unexpected terminal diagnostic identity: ' + $stage.name) }
        if ($stage.required_flag -and !$stageResult.($stage.required_flag)) { throw ('Independent diagnostic verification failed: ' + $stage.name) }
        $stageRecord.result = 'verified_terminal'
        $stageRecord.report_sha256 = (Get-FileHash -LiteralPath $stageReport -Algorithm SHA256).Hash.ToLowerInvariant()
        Save-Report
        Write-Output ('DIAGNOSTIC_STAGE_COMPLETE ' + $stage.name)
    }
    $nativeProof = Get-Content -LiteralPath (Join-Path $manifest.stages[-1].out 'report.json') -Raw | ConvertFrom-Json
    $report.native16_32_convergence_passed = $nativeProof.native16_32_convergence_passed
    $report.eligible_for_later_source_statistics = $nativeProof.eligible_for_later_source_statistics
    $report.result = 'diagnostics_complete_not_timbre_or_sustained_acceptance'
    $report.finished_utc = [DateTime]::UtcNow.ToString('o')
    Save-Report
    Write-Output ('DIAGNOSTIC_FOLLOWTHROUGH_COMPLETE eligible=' + $report.eligible_for_later_source_statistics)
} catch {
    $report.result = 'failed'
    $report.error = $_.ToString()
    $report.finished_utc = [DateTime]::UtcNow.ToString('o')
    Save-Report
    Write-Error $_
    exit 1
}

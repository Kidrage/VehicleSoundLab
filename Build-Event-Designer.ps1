$ErrorActionPreference = 'Stop'
$vslEventBuild = Join-Path $PSScriptRoot 'build-event-synth-v4'
function Get-VslEventInputs {
    $vslEventInputs = [ordered]@{}
    $vslEventFiles = @(Get-ChildItem -LiteralPath (Join-Path $PSScriptRoot 'modules/event_synth') -File | Where-Object { $_.Extension -in '.c','.h' -or $_.Name -eq 'CMakeLists.txt' })
    $vslEventFiles += Get-Item -LiteralPath (Join-Path $PSScriptRoot 'experiments/event_synth_v1/author_bridge.c'),(Join-Path $PSScriptRoot 'experiments/event_synth_v1/CMakeLists.txt'),$PSCommandPath
    foreach ($vslEventFile in ($vslEventFiles | Sort-Object FullName)) {
        $vslEventName = $vslEventFile.FullName.Substring($PSScriptRoot.Length + 1).Replace('\','/')
        $vslEventInputs[$vslEventName] = (Get-FileHash -LiteralPath $vslEventFile.FullName -Algorithm SHA256).Hash.ToLower()
    }
    return $vslEventInputs
}
$vslEventBefore = Get-VslEventInputs
cmake -S (Join-Path $PSScriptRoot 'experiments/event_synth_v1') -B $vslEventBuild -G 'Visual Studio 17 2022' -A x64
if ($LASTEXITCODE) { exit $LASTEXITCODE }
cmake --build $vslEventBuild --config Release --parallel 2
if ($LASTEXITCODE) { exit $LASTEXITCODE }
ctest --test-dir $vslEventBuild -C Release --output-on-failure
if ($LASTEXITCODE) { exit $LASTEXITCODE }
$vslEventAfter = Get-VslEventInputs
if (($vslEventBefore | ConvertTo-Json -Compress) -ne ($vslEventAfter | ConvertTo-Json -Compress)) { throw 'Event sources changed during the build; rebuild before authoring.' }
$vslEventDll = Join-Path $vslEventBuild 'bin/Release/vsl_event_author_bridge.dll'
$vslEventBinding = [ordered]@{ schema='vsl.event-author-build/1'; dll_sha256=(Get-FileHash -LiteralPath $vslEventDll -Algorithm SHA256).Hash.ToLower(); sources=$vslEventAfter }
[System.IO.File]::WriteAllText((Join-Path $vslEventBuild 'bin/Release/event-author-build.json'),($vslEventBinding | ConvertTo-Json -Depth 5),[System.Text.UTF8Encoding]::new($false))
exit 0

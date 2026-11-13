$ErrorActionPreference = 'Stop'
$vslIdleDriveBuild = Join-Path $PSScriptRoot 'build-idle-drive-v1'
cmake -S (Join-Path $PSScriptRoot 'experiments/idle_drive_v1') -B $vslIdleDriveBuild -G 'Visual Studio 17 2022' -A x64
if ($LASTEXITCODE) { exit $LASTEXITCODE }
cmake --build $vslIdleDriveBuild --config Release --parallel 2
if ($LASTEXITCODE) { exit $LASTEXITCODE }
ctest --test-dir $vslIdleDriveBuild -C Release --output-on-failure
exit $LASTEXITCODE

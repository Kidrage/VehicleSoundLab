$ErrorActionPreference = 'Stop'
$vslFineIdleBuild = Join-Path $PSScriptRoot 'build-fine-idle-drive-v1'
cmake -S (Join-Path $PSScriptRoot 'experiments/fine_idle_drive_v1') -B $vslFineIdleBuild -G 'Visual Studio 17 2022' -A x64
if ($LASTEXITCODE) { exit $LASTEXITCODE }
cmake --build $vslFineIdleBuild --config Release --parallel 2
if ($LASTEXITCODE) { exit $LASTEXITCODE }
ctest --test-dir $vslFineIdleBuild -C Release --output-on-failure
exit $LASTEXITCODE

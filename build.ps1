param([string]$BuildDirectory = 'build-v020')
$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$buildRoot = Join-Path $projectRoot $BuildDirectory
cmake -S $projectRoot -B $buildRoot -G 'Visual Studio 17 2022' -A x64
if ($LASTEXITCODE) { exit $LASTEXITCODE }
cmake --build $buildRoot --config Release --parallel
if ($LASTEXITCODE) { exit $LASTEXITCODE }
ctest --test-dir $buildRoot -C Release --output-on-failure
exit $LASTEXITCODE

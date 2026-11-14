$ErrorActionPreference = 'Stop'
$vslCatalogBuild = Join-Path $PSScriptRoot 'build-bench-load-v1'
cmake -S (Join-Path $PSScriptRoot 'experiments/catalog_drive_v1') -B $vslCatalogBuild -G 'Visual Studio 17 2022' -A x64
if ($LASTEXITCODE) { exit $LASTEXITCODE }
cmake --build $vslCatalogBuild --config Release --parallel 2
if ($LASTEXITCODE) { exit $LASTEXITCODE }
ctest --test-dir $vslCatalogBuild -C Release --output-on-failure
exit $LASTEXITCODE

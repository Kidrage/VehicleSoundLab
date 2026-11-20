param([ValidateSet('production','profile','diagnostic','generic')][string]$Mode='production',[switch]$Test)
$ErrorActionPreference='Stop'
$vslRoot=$PSScriptRoot
$vslBuild=Join-Path $vslRoot ('build/'+$Mode)
$vslOptions=@()
if($Mode -eq 'profile'){$vslOptions+='-DVSL_PROFILE=ON'}
if($Mode -eq 'diagnostic'){$vslOptions+='-DVSL_CAPTURE_MODULES=ON'}
if($Mode -eq 'generic'){$vslOptions+='-DVSL_STATIC_RUNTIME=OFF'}
cmake -S $vslRoot -B $vslBuild -G 'Visual Studio 17 2022' -A x64 @vslOptions
if($LASTEXITCODE -ne 0){throw 'CMake configure failed'}
cmake --build $vslBuild --config Release -j 8
if($LASTEXITCODE -ne 0){throw 'Build failed'}
if($Test){ctest --test-dir $vslBuild -C Release --output-on-failure;if($LASTEXITCODE -ne 0){throw 'Checks failed'}}
Write-Host "Built $Mode at $vslBuild/bin/Release. Render from the source root so relative assets resolve."


param([switch]$SequentialOnly)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$build = Join-Path $root 'build'
New-Item -ItemType Directory -Force -Path $build | Out-Null
$compiler = (Get-Command g++ -ErrorAction Stop).Source
$compilerDir = Split-Path $compiler -Parent
$flags = @('-std=c++17', '-O2')

if (-not $SequentialOnly) {
    $flags += @('-fopenmp', '-DHAVE_OPENMP=1')
    $pthreadLib = Join-Path (Split-Path $compilerDir -Parent) 'lib\libpthread.a'
    if (-not (Test-Path -LiteralPath $pthreadLib)) {
        $dll = Join-Path $compilerDir 'pthreadGC-3.dll'
        if (-not (Test-Path -LiteralPath $dll)) {
            throw 'OpenMP needs a pthread import library or pthreadGC-3.dll. Use -SequentialOnly for the CPU baseline.'
        }
        $lines = & (Join-Path $compilerDir 'objdump.exe') -p $dll
        $start = ($lines | Select-String -Pattern '^\[Ordinal/Name Pointer\] Table$').LineNumber
        if (-not $start) { throw 'Could not read pthread DLL exports' }
        $symbols = foreach ($line in $lines[($start)..($lines.Length - 1)]) {
            if ($line -match '^\s*\[\s*\d+\]\s+(\S+)') { $Matches[1] }
            elseif ($line -match '^The Import Tables') { break }
        }
        if ($symbols.Count -lt 100) { throw 'Incomplete pthread DLL export table' }
        $def = Join-Path $build 'pthread.def'
        @('LIBRARY pthreadGC-3.dll', 'EXPORTS') + $symbols | Set-Content -LiteralPath $def -Encoding ascii
        & (Join-Path $compilerDir 'dlltool.exe') -d $def -D pthreadGC-3.dll -l (Join-Path $build 'libpthread.a')
        if ($LASTEXITCODE -ne 0) { throw 'Failed to create pthread import library' }
        $flags += "-L$build"
    }
}

& $compiler @flags (Join-Path $root 'cpp\main.cpp') (Join-Path $root 'cpp\thermal_cpu.cpp') '-o' (Join-Path $build 'thermal_engine.exe')
if ($LASTEXITCODE -ne 0) { throw 'Native build failed' }
& (Join-Path $build 'thermal_engine.exe') --help

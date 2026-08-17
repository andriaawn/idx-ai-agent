$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) {
    throw "Project Python interpreter was not found: $pythonPath. Do not fall back to system Python; create or repair .venv only when explicitly instructed."
}

$pythonPath = (Resolve-Path -LiteralPath $pythonPath).Path

Push-Location $projectRoot
try {
    Write-Host "Python executable: $pythonPath"
    & $pythonPath --version
    & $pythonPath -m pip --version
    & $pythonPath -c "import sys; print('sys.executable:', sys.executable); print('sys.prefix:', sys.prefix); print('sys.base_prefix:', sys.base_prefix)"

    & $pythonPath -m compileall -q src tests
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    & $pythonPath -m unittest discover -s tests -p "test_*.py"
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}

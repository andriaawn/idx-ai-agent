$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) {
    throw "Project Python interpreter was not found: $pythonPath. Do not fall back to system Python."
}

Push-Location $projectRoot
try {
    & $pythonPath -m unittest discover -s tests -p "test_*.py"
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}

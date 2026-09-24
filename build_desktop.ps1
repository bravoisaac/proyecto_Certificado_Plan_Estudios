$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Test-PythonCommand {
    param(
        [string]$Executable,
        [string[]]$Prefix
    )

    try {
        & $Executable @Prefix -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" 2>$null
        return $LASTEXITCODE -eq 0
    } catch {
        return $false
    }
}

$pythonExecutable = $null
$pythonPrefix = @()
if ((Get-Command py -ErrorAction SilentlyContinue) -and (Test-PythonCommand "py" @("-3"))) {
    $pythonExecutable = "py"
    $pythonPrefix = @("-3")
} elseif ((Get-Command python -ErrorAction SilentlyContinue) -and (Test-PythonCommand "python" @())) {
    $pythonExecutable = "python"
}

if (-not $pythonExecutable) {
    throw "No se encontró Python 3.10 o superior. Instálalo desde https://www.python.org/downloads/windows/ y vuelve a ejecutar este archivo."
}

$buildEnvironment = Join-Path $PSScriptRoot ".venv-build"
if (-not (Test-Path (Join-Path $buildEnvironment "Scripts\python.exe"))) {
    & $pythonExecutable @pythonPrefix -m venv $buildEnvironment
}

$buildPython = Join-Path $buildEnvironment "Scripts\python.exe"
& $buildPython -m pip install --disable-pip-version-check -r requirements-desktop.txt
& $buildPython -m PyInstaller `
    --name "EquivalenciasPlanEstudios" `
    --onefile `
    --windowed `
    --clean `
    --noconfirm `
    --add-data "index.html;." `
    --add-data "static;static" `
    desktop.py

Write-Host ""
Write-Host "Ejecutable creado en: $PSScriptRoot\dist\EquivalenciasPlanEstudios.exe" -ForegroundColor Green

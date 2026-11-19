$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$existing = Get-CimInstance Win32_Process |
    Where-Object {
        $_.Name -match '^python(w)?\.exe$' -and
        $_.CommandLine -match 'nova_widget\.py'
    }

if ($existing) {
    Write-Host "Nova is already running. Close the existing widget first."
    exit 0
}

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
$widget = Join-Path $PSScriptRoot "nova_widget.py"

if (!(Test-Path $python) -or !(Test-Path $widget)) {
    throw "Nova files were not found. Check the project folder."
}

& $python -u $widget

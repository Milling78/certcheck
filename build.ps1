#Requires -Version 5.1
<#
.SYNOPSIS
    Build the standalone certcheck executables via PyInstaller.
.DESCRIPTION
    Produces two single-file, self-contained Windows executables that need no
    Python install:
        dist\certcheck.exe      — command-line tool
        dist\certcheck-gui.exe  — point-and-click GUI (scan + Excel export)
    Run from a normal (non-admin) terminal.
.PARAMETER SkipDeps
    Skip the pip install step (reuse what's already installed).
.PARAMETER CliOnly
    Build only the CLI exe.
.PARAMETER GuiOnly
    Build only the GUI exe.
.EXAMPLE
    .\build.ps1
    .\build.ps1 -SkipDeps -GuiOnly
#>
param([switch]$SkipDeps, [switch]$CliOnly, [switch]$GuiOnly)

$ErrorActionPreference = 'Stop'
Set-Location -Path $PSScriptRoot

$py = (Get-Command python -ErrorAction Stop).Source
Write-Host "Using $py" -ForegroundColor Cyan

if (-not $SkipDeps) {
    Write-Host "Installing build dependencies..." -ForegroundColor Cyan
    & $py -m pip install --quiet --upgrade pyinstaller cryptography openpyxl
}

function Build-Spec($spec, $expectedExe) {
    Write-Host "Building $expectedExe..." -ForegroundColor Cyan
    & $py -m PyInstaller --clean --noconfirm $spec
    $path = Join-Path $PSScriptRoot "dist\$expectedExe"
    if (Test-Path $path) {
        Write-Host "Built $path" -ForegroundColor Green
    } else {
        Write-Error "Build finished but $path not found"
        exit 1
    }
}

if (-not $GuiOnly) { Build-Spec 'certcheck.spec'     'certcheck.exe' }
if (-not $CliOnly) { Build-Spec 'certcheck_gui.spec' 'certcheck-gui.exe' }

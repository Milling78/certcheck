#Requires -Version 5.1
<#
.SYNOPSIS
    Build a standalone certcheck.exe via PyInstaller.
.DESCRIPTION
    Produces dist\certcheck.exe — a single self-contained Windows executable that
    needs no Python install. Run from a normal (non-admin) terminal.
.PARAMETER SkipDeps
    Skip the pip install step (reuse what's already installed).
.EXAMPLE
    .\build.ps1
    .\build.ps1 -SkipDeps
#>
param([switch]$SkipDeps)

$ErrorActionPreference = 'Stop'
Set-Location -Path $PSScriptRoot

$py = (Get-Command python -ErrorAction Stop).Source
Write-Host "Using $py" -ForegroundColor Cyan

if (-not $SkipDeps) {
    Write-Host "Installing build dependencies..." -ForegroundColor Cyan
    & $py -m pip install --quiet --upgrade pyinstaller cryptography
}

Write-Host "Building certcheck.exe..." -ForegroundColor Cyan
& $py -m PyInstaller --clean --noconfirm certcheck.spec

$exe = Join-Path $PSScriptRoot 'dist\certcheck.exe'
if (Test-Path $exe) {
    Write-Host "Built $exe" -ForegroundColor Green
} else {
    Write-Error "Build finished but $exe not found"
    exit 1
}

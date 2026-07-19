Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

Set-Location (Split-Path $PSScriptRoot -Parent)
python -m compileall app
python scripts/check_deps.py
python -m pytest

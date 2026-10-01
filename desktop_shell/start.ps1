$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$env:PYTHONPATH = "$Root\desktop_shell" + $(if ($env:PYTHONPATH) { ";$env:PYTHONPATH" } else { "" })
python -m uvicorn app:app --app-dir desktop_shell --host 127.0.0.1 --port 8765

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
& "$PSScriptRoot\Verify-Pack.ps1"
if ($LASTEXITCODE -ne 0) { throw 'Checksum verification failed' }
if ($env:PROCESSOR_ARCHITECTURE -ne 'AMD64') { throw 'Requires Windows x64 on Intel/AMD' }
$distros = (& wsl.exe --list --quiet 2>$null) -replace "`0", ''
if ($LASTEXITCODE -ne 0) { throw 'Install WSL MSI and reboot first' }
if ($distros | Where-Object { $_.Trim() -eq 'QAIWorkshop' }) { throw 'QAIWorkshop already exists; refusing to overwrite' }
$destination = Join-Path $env:LOCALAPPDATA 'QAI\WSL'
if (Test-Path $destination) { throw "Destination exists: $destination. Refusing to overwrite." }
New-Item -ItemType Directory -Path $destination | Out-Null
& wsl.exe --import QAIWorkshop $destination "$PSScriptRoot\installers\ubuntu-qai-x64.tar.gz" --version 2
if ($LASTEXITCODE -ne 0) { throw 'WSL import failed; keep the error and contact the facilitator' }
Write-Host 'Imported QAIWorkshop. Enable its Docker Desktop WSL integration, then follow WINDOWS-SETUP.md.'

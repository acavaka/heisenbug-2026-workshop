$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$manifest = Get-Content -LiteralPath "$PSScriptRoot\USB-MANIFEST.json" -Raw | ConvertFrom-Json
foreach ($item in $manifest.files) {
    $path = Join-Path $PSScriptRoot $item.path
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Missing: $($item.path)" }
    if ((Get-Item -LiteralPath $path).Length -ne $item.size) { throw "Wrong size: $($item.path)" }
    if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $item.sha256) { throw "Wrong SHA256: $($item.path)" }
}
Write-Host "PASS: $($manifest.files.Count) files verified."
exit 0

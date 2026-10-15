# Reproduce BUG-1024 on Windows (requires frontend port-forward already running).
# Usage: .\hack\reproduce-bug-1024.ps1
$ErrorActionPreference = "Stop"

$ClusterName = if ($env:CLUSTER_NAME) { $env:CLUSTER_NAME } else { "qai-boutique" }
$Context = "kind-$ClusterName"
$ProductId = if ($env:PRODUCT_ID) { $env:PRODUCT_ID } else { "OLJCESPC7Z" }
$NewUnits = if ($env:NEW_UNITS) { $env:NEW_UNITS } else { "15" }
$NewNanos = if ($env:NEW_NANOS) { $env:NEW_NANOS } else { "990000000" }
$FrontendUrl = if ($env:FRONTEND_URL) { $env:FRONTEND_URL } else { "http://127.0.0.1:8080" }

kubectl config use-context $Context | Out-Null

try {
  Invoke-WebRequest -Uri $FrontendUrl -UseBasicParsing | Out-Null
} catch {
  throw "Frontend not reachable at $FrontendUrl. Run .\hack\ports.ps1 first."
}

Write-Host "==> Port-forward catalog admin :18081"
$pf = Start-Process -FilePath kubectl -ArgumentList @(
  "port-forward","--address=127.0.0.1","svc/productcatalogservice","18081:8081"
) -PassThru -WindowStyle Hidden
Start-Sleep -Seconds 2

try {
  $session = New-Object Microsoft.PowerShell.Commands.WebRequestSession
  Invoke-WebRequest -Uri "$FrontendUrl/product/$ProductId" -WebSession $session -UseBasicParsing | Out-Null
  Invoke-WebRequest -Uri "$FrontendUrl/cart" -Method POST -WebSession $session -UseBasicParsing `
    -ContentType "application/x-www-form-urlencoded" `
    -Body "product_id=$ProductId&quantity=1" | Out-Null
  Invoke-WebRequest -Uri "$FrontendUrl/cart" -WebSession $session -UseBasicParsing | Out-Null

  Write-Host "==> Update price units=$NewUnits"
  Invoke-WebRequest -Method POST -UseBasicParsing `
    -Uri "http://127.0.0.1:18081/admin/update_price?id=$ProductId&units=$NewUnits&nanos=$NewNanos" | Out-Null

  Write-Host "==> Logs:"
  kubectl logs deploy/productcatalogservice --tail=40
} finally {
  if ($pf -and -not $pf.HasExited) { Stop-Process -Id $pf.Id -Force }
}

Write-Host "Done. Look for cache hit/miss and price updated in logs."

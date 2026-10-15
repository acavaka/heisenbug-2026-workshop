# Raise Kind cluster + Online Boutique (Windows PowerShell)
# Usage: .\hack\up.ps1
# Prefer Git Bash + ./hack/up.sh when possible (no ExecutionPolicy / stderr issues).
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$ClusterName = if ($env:CLUSTER_NAME) { $env:CLUSTER_NAME } else { "qai-boutique" }
$Context = "kind-$ClusterName"
$Manifest = Join-Path $Root "release\kubernetes-manifests.yaml"

function Need($cmd) {
  if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) {
    throw "ERROR: '$cmd' not found in PATH"
  }
}

# Run native CLI without treating stderr as terminating (kubectl/kind noise).
function Invoke-Native {
  param([scriptblock]$Command)
  $prev = $ErrorActionPreference
  $ErrorActionPreference = "Continue"
  & $Command 2>&1 | Out-Host
  $code = $LASTEXITCODE
  $ErrorActionPreference = $prev
  return $code
}

Need docker
Need kind
Need kubectl

docker info | Out-Null
if ($LASTEXITCODE -ne 0) { throw "ERROR: Docker is not running. Start Docker Desktop (WSL2 backend)." }

# kind prints "No kind clusters found." to stderr when empty
$prevEap = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$clusterOut = & kind get clusters 2>&1
$ErrorActionPreference = $prevEap
$clusters = @(
  $clusterOut |
    Where-Object { $_ -isnot [System.Management.Automation.ErrorRecord] } |
    ForEach-Object { "$_".Trim() } |
    Where-Object { $_ -and ($_ -notmatch 'No kind clusters') }
)

if ($clusters -notcontains $ClusterName) {
  Write-Host "==> Creating Kind cluster '$ClusterName'..."
  $rc = Invoke-Native { kind create cluster --name $ClusterName }
  if ($rc -ne 0) { throw "ERROR: kind create cluster failed" }
} else {
  Write-Host "==> Kind cluster '$ClusterName' already exists"
}

Invoke-Native { kubectl config use-context $Context } | Out-Null

Write-Host "==> Applying Online Boutique manifests..."
$rc = Invoke-Native { kubectl apply -f $Manifest }
if ($rc -ne 0) { throw "ERROR: kubectl apply failed" }

Write-Host "==> Scaling loadgenerator to 0..."
Invoke-Native { kubectl scale deployment/loadgenerator --replicas=0 } | Out-Null

Write-Host "==> Waiting for deployments (first pull can take many minutes)..."
$deps = @(
  "frontend","productcatalogservice","cartservice","checkoutservice",
  "paymentservice","currencyservice","shippingservice","emailservice",
  "recommendationservice","adservice","redis-cart"
)
# Match bash up.sh: wait failures are non-fatal (images may still be pulling).
foreach ($d in $deps) {
  Write-Host "  wait deployment/$d ..."
  $null = Invoke-Native { kubectl wait --for=condition=available --timeout=600s "deployment/$d" }
}

Invoke-Native { kubectl get pods }

Write-Host ""
Write-Host "Done. Context: $Context"
Write-Host "Check: kubectl get pods   (all Running = OK even if some waits timed out)"
Write-Host "Next: .\hack\ports.ps1   or Git Bash: ./hack/ports.sh"
Write-Host "      then open http://127.0.0.1:8080"
Write-Host "Tip: prefer Git Bash ./hack/up.sh to avoid PowerShell stderr issues."

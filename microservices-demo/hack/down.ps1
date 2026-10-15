# Tear down Kind cluster (or only manifests).
# Usage: .\hack\down.ps1 [-ManifestsOnly]
param([switch]$ManifestsOnly)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$ClusterName = if ($env:CLUSTER_NAME) { $env:CLUSTER_NAME } else { "qai-boutique" }
$Context = "kind-$ClusterName"
$Manifest = Join-Path $Root "release\kubernetes-manifests.yaml"

if ($ManifestsOnly) {
  kubectl --context $Context delete -f $Manifest --ignore-not-found
  Write-Host "Manifests deleted from $Context"
  exit 0
}

$clusters = kind get clusters 2>$null
if ($clusters -contains $ClusterName) {
  kind delete cluster --name $ClusterName
  Write-Host "Deleted Kind cluster '$ClusterName'"
} else {
  Write-Host "Cluster '$ClusterName' not found"
}

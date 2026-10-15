# Port-forward Boutique frontend to http://127.0.0.1:8080
# Usage: .\hack\ports.ps1
$ErrorActionPreference = "Stop"

$ClusterName = if ($env:CLUSTER_NAME) { $env:CLUSTER_NAME } else { "qai-boutique" }
$Context = "kind-$ClusterName"
$LocalPort = if ($env:LOCAL_PORT) { $env:LOCAL_PORT } else { "8080" }

kubectl config use-context $Context | Out-Null
Write-Host "Forwarding svc/frontend -> http://127.0.0.1:$LocalPort"
Write-Host "Stop with Ctrl+C"
kubectl port-forward --address=127.0.0.1 svc/frontend "${LocalPort}:80"

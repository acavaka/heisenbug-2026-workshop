#!/usr/bin/env bash
set -euo pipefail
pack="$(cd "$(dirname "$0")" && pwd)"
[[ "$(uname -s)/$(uname -m)" == "Linux/x86_64" ]] || { echo 'Use WSL2 x64'; exit 1; }
[[ "$(id -un)" == qai ]] || { echo 'Run as the WSL user qai'; exit 1; }
python3 "$pack/verify_pack.py"
project="$HOME/qai-workshop/qai-participant"
[[ ! -e "$project" ]] || { echo "Project exists: $project. Refusing to overwrite."; exit 1; }
mkdir -p "$HOME/qai-workshop" "$HOME/.local/bin"
unzip -q "$pack/qai-participant.zip" -d "$HOME/qai-workshop"
for tool in kind kubectl k8sgpt; do
  [[ ! -e "$HOME/.local/bin/$tool" ]] || { echo "Tool exists: $tool; refusing overwrite"; exit 1; }
  install -m 755 "$pack/tools/$tool" "$HOME/.local/bin/$tool"
done
cd "$project"
python3 workshop/offline/install.py --wheels "$pack/python-wheels"
cp workshop/.env.example workshop/.env
chmod 600 workshop/.env
cat > "$HOME/qai-env.sh" <<'ENV'
export PATH="$HOME/qai-workshop/qai-participant/workshop/.venv/bin:$HOME/.local/bin:$PATH"
export KUBECONFIG="$HOME/qai-workshop/qai-participant/workshop/.local/kind.kubeconfig"
export KUBECTL_CONTEXT=kind-qai-boutique
ENV
cat > "$HOME/.local/bin/qai-application-mcp" <<'MCP'
#!/usr/bin/env bash
set -euo pipefail
source "$HOME/qai-env.sh"
cd "$HOME/qai-workshop/qai-participant"
exec python workshop/application_mcp.py "$@"
MCP
cat > "$HOME/.local/bin/qai-k8sgpt-mcp" <<'MCP'
#!/usr/bin/env bash
set -euo pipefail
source "$HOME/qai-env.sh"
cd "$HOME/qai-workshop/qai-participant"
if [[ -f "$HOME/qai-training-readonly.kubeconfig" ]]; then
  export QAI_KUBECONFIG="$HOME/qai-training-readonly.kubeconfig"
fi
exec python workshop/mcp_gateway.py "$@"
MCP
chmod 755 "$HOME/.local/bin/qai-application-mcp" "$HOME/.local/bin/qai-k8sgpt-mcp"
echo 'Ready. Run: source ~/qai-env.sh; cd ~/qai-workshop/qai-participant'
echo 'Then follow WINDOWS-SETUP.md. Cluster has not been started.'

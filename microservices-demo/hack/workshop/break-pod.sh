#!/usr/bin/env bash
# Демо k8sgpt: сломать под и вернуть обратно.
#   ./hack/workshop/break-pod.sh break   # paymentservice → ImagePullBackOff
#   ./hack/workshop/break-pod.sh fix
#   ./hack/workshop/break-pod.sh status
set -euo pipefail
CTX="${KUBECTL_CONTEXT:-kind-qai-boutique}"
DEPLOY="${1:-status}"
TARGET="${TARGET_DEPLOY:-paymentservice}"

case "$DEPLOY" in
  break)
    kubectl --context "$CTX" set image "deploy/$TARGET" server="boutique/$TARGET:does-not-exist"
    echo "Ждём ImagePullBackOff..."
    sleep 5
    kubectl --context "$CTX" get pods -l app="$TARGET"
    echo
    echo "Теперь: k8sgpt analyze --explain --kubecontext $CTX  или  python workshop/qai_tool.py k8sgpt_analyze"
    ;;
  fix)
    kubectl --context "$CTX" rollout undo "deploy/$TARGET"
    kubectl --context "$CTX" rollout status "deploy/$TARGET" --timeout=120s
    ;;
  status)
    kubectl --context "$CTX" get pods -l app="$TARGET"
    ;;
  *)
    echo "usage: $0 break|fix|status" >&2; exit 2;;
esac

#!/usr/bin/env bash
# =============================================================================
#  scripts/create-secrets.sh
#
#  Reads SigilHive/.env and creates (or updates) a Kubernetes Secret in the
#  sigilhive namespace. Every honeypot pod mounts this secret via envFrom.
#
#  This script is IDEMPOTENT — safe to re-run any time .env changes.
#
#  Usage:
#    export GCP_PROJECT_ID="MY_PROJECT_ID"
#    bash scripts/create-secrets.sh
#
#  To point at a different .env file:
#    ENV_FILE=path/to/.env bash scripts/create-secrets.sh
# =============================================================================

set -euo pipefail

PROJECT_ID="${GCP_PROJECT_ID:-MY_PROJECT_ID}"
REGION="asia-south1"
CLUSTER_NAME="sigilhive-cluster"
NAMESPACE="sigilhive"
SECRET_NAME="sigilhive-secrets"

# Path to .env — relative to the repo root (22CS13-SigilHive/)
# Your real file: 22CS13-SigilHive/SigilHive/.env
ENV_FILE="${ENV_FILE:-SigilHive/.env}"

echo ""
echo "▶ Fetching GKE credentials..."
gcloud container clusters get-credentials "${CLUSTER_NAME}" \
  --region="${REGION}" \
  --project="${PROJECT_ID}" \
  --quiet

echo "▶ Ensuring namespace '${NAMESPACE}' exists..."
kubectl create namespace "${NAMESPACE}" \
  --dry-run=client -o yaml | kubectl apply -f -

if [[ ! -f "${ENV_FILE}" ]]; then
  echo ""
  echo "❌  .env file not found at: ${ENV_FILE}"
  echo ""
  echo "   Create it first:"
  echo "     cp SigilHive/.env.example SigilHive/.env"
  echo "     nano SigilHive/.env"
  echo ""
  exit 1
fi

echo "▶ Creating/updating Kubernetes Secret '${SECRET_NAME}' from ${ENV_FILE}..."

# --from-env-file automatically skips blank lines and # comments
kubectl create secret generic "${SECRET_NAME}" \
  --namespace="${NAMESPACE}" \
  --from-env-file="${ENV_FILE}" \
  --dry-run=client -o yaml \
  | kubectl apply -f -

echo ""
echo "✅  Secret '${SECRET_NAME}' is up to date in namespace '${NAMESPACE}'."
echo ""
echo "   Verify:  kubectl get secret ${SECRET_NAME} -n ${NAMESPACE}"
echo ""
echo "   If pods are already running, restart them to pick up new values:"
echo "     kubectl rollout restart deployment -n ${NAMESPACE}"
echo ""
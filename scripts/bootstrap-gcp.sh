#!/usr/bin/env bash
# =============================================================================
#  scripts/bootstrap-gcp.sh
#
#  Run this ONCE from your local machine to create all GCP infrastructure.
#  After this script you never need to run it again unless you tear down
#  the project entirely.
#
#  Prerequisites:
#    - gcloud CLI installed  →  https://cloud.google.com/sdk/docs/install
#    - Authenticated         →  gcloud auth login
#    - Billing enabled on the project
#
#  Usage:
#    export GCP_PROJECT_ID="MY_PROJECT_ID"
#    bash scripts/bootstrap-gcp.sh
# =============================================================================

set -euo pipefail

# ── EDIT THESE TWO LINES ──────────────────────────────────────────────────────
GITHUB_ORG="YOUR_GITHUB_ORG"       # your GitHub username or org  e.g. "myorg"
GITHUB_REPO="22CS13-SigilHive"     # your repository name exactly as it appears on GitHub
# ─────────────────────────────────────────────────────────────────────────────

# ── Infrastructure config (change only if you want different names) ───────────
PROJECT_ID="${GCP_PROJECT_ID:-MY_PROJECT_ID}"
REGION="asia-south1"
ZONE="asia-south1-a"
CLUSTER_NAME="sigilhive-cluster"
AR_REPO="sigilhive"                 # Artifact Registry repository name
SA_NAME="sigilhive-deployer"        # Service Account name
WIF_POOL="github-pool"              # Workload Identity Pool name
WIF_PROVIDER="github-provider"      # Workload Identity Provider name
# ─────────────────────────────────────────────────────────────────────────────

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║        SigilHive — GCP Bootstrap (asia-south1)          ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""
echo "  Project  : ${PROJECT_ID}"
echo "  Region   : ${REGION} (Mumbai)"
echo "  Cluster  : ${CLUSTER_NAME}"
echo "  GitHub   : ${GITHUB_ORG}/${GITHUB_REPO}"
echo ""

# ── 1. Set active project ─────────────────────────────────────────────────────
echo "▶ [1/7] Setting active project..."
gcloud config set project "${PROJECT_ID}"

# ── 2. Enable required APIs ───────────────────────────────────────────────────
echo "▶ [2/7] Enabling GCP APIs (this takes ~1 minute)..."
gcloud services enable \
  container.googleapis.com \
  artifactregistry.googleapis.com \
  iam.googleapis.com \
  iamcredentials.googleapis.com \
  cloudresourcemanager.googleapis.com \
  --project="${PROJECT_ID}"
echo "   APIs enabled."

# ── 3. Artifact Registry ──────────────────────────────────────────────────────
echo "▶ [3/7] Creating Artifact Registry repository: ${AR_REPO}..."
gcloud artifacts repositories create "${AR_REPO}" \
  --repository-format=docker \
  --location="${REGION}" \
  --description="SigilHive honeypot Docker images" \
  --project="${PROJECT_ID}" \
  2>/dev/null \
  && echo "   Created: ${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPO}" \
  || echo "   Already exists — skipping."

# ── 4. GKE Autopilot cluster ─────────────────────────────────────────────────
echo "▶ [4/7] Creating GKE Autopilot cluster: ${CLUSTER_NAME}..."
echo "   Region: ${REGION} — this takes 8–12 minutes on first run."
gcloud container clusters create-auto "${CLUSTER_NAME}" \
  --region="${REGION}" \
  --project="${PROJECT_ID}" \
  2>/dev/null \
  && echo "   Cluster created." \
  || echo "   Already exists — skipping."

# Configure kubectl to point at the new cluster
gcloud container clusters get-credentials "${CLUSTER_NAME}" \
  --region="${REGION}" \
  --project="${PROJECT_ID}"
echo "   kubectl context set to ${CLUSTER_NAME}."

# ── 5. Service Account ────────────────────────────────────────────────────────
echo "▶ [5/7] Creating Service Account: ${SA_NAME}..."
gcloud iam service-accounts create "${SA_NAME}" \
  --display-name="SigilHive GitHub Actions Deployer" \
  --project="${PROJECT_ID}" \
  2>/dev/null || echo "   Already exists — skipping."

SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

echo "   Granting IAM roles to ${SA_EMAIL}..."
for ROLE in \
  "roles/container.developer" \
  "roles/artifactregistry.writer" \
  "roles/iam.serviceAccountTokenCreator"; do
  gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="${ROLE}" \
    --quiet
  echo "   ✓ ${ROLE}"
done

# ── 6. Workload Identity Federation ──────────────────────────────────────────
echo "▶ [6/7] Setting up Workload Identity Federation (keyless auth)..."

# Create pool
gcloud iam workload-identity-pools create "${WIF_POOL}" \
  --location="global" \
  --display-name="GitHub Actions Pool" \
  --project="${PROJECT_ID}" \
  2>/dev/null || echo "   Pool already exists — skipping."

# Create OIDC provider scoped to THIS repo only
gcloud iam workload-identity-pools providers create-oidc "${WIF_PROVIDER}" \
  --location="global" \
  --workload-identity-pool="${WIF_POOL}" \
  --display-name="GitHub Actions OIDC Provider" \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.actor=assertion.actor" \
  --attribute-condition="assertion.repository=='${GITHUB_ORG}/${GITHUB_REPO}'" \
  --project="${PROJECT_ID}" \
  2>/dev/null || echo "   Provider already exists — skipping."

# Allow only this specific repo's Actions to impersonate the SA
POOL_RESOURCE=$(gcloud iam workload-identity-pools describe "${WIF_POOL}" \
  --location="global" \
  --project="${PROJECT_ID}" \
  --format="value(name)")

gcloud iam service-accounts add-iam-policy-binding "${SA_EMAIL}" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/${POOL_RESOURCE}/attribute.repository/${GITHUB_ORG}/${GITHUB_REPO}" \
  --project="${PROJECT_ID}" \
  --quiet
echo "   WIF configured."

# ── 7. Collect output values for GitHub Secrets ───────────────────────────────
echo "▶ [7/7] Collecting GitHub Secret values..."

PROVIDER_RESOURCE=$(gcloud iam workload-identity-pools providers describe "${WIF_PROVIDER}" \
  --location="global" \
  --workload-identity-pool="${WIF_POOL}" \
  --project="${PROJECT_ID}" \
  --format="value(name)")

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════════════════════════╗"
echo "║  ✅  Bootstrap complete!  Next step → add these GitHub Secrets:     ║"
echo "╠══════════════════════════════════════════════════════════════════════╣"
echo "║                                                                      ║"
echo "║  Go to: GitHub repo → Settings → Secrets → Actions → New secret     ║"
echo "║                                                                      ║"
printf "║  %-20s = %-47s ║\n" "GCP_PROJECT_ID"      "${PROJECT_ID}"
printf "║  %-20s = %-47s ║\n" "WIF_PROVIDER"        "${PROVIDER_RESOURCE}"
printf "║  %-20s = %-47s ║\n" "WIF_SERVICE_ACCOUNT" "${SA_EMAIL}"
echo "║                                                                      ║"
echo "║  Then run:  bash scripts/create-secrets.sh                          ║"
echo "╚══════════════════════════════════════════════════════════════════════╝"
echo ""
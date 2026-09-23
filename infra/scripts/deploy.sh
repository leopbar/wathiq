#!/usr/bin/env bash
#
# Deploy Wathiq to Azure, end to end.
#
#   ./infra/scripts/deploy.sh rg-wathiq-dev eastus2
#
# Six steps: create the group, deploy the infrastructure, put the secrets in Key Vault, build
# and push the images, install the chart, print how to reach it.
#
# ─────────────────────────────────────────────────────────────────────────────
# SAFETY. This subscription contains a working system in `filingsiq-rg`.
#
# Set WATHIQ_SKIP_AI=1 to leave the Cognitive Services accounts and model deployments untouched
# and deploy only the rest. Useful when iterating on the cluster, and necessary when Azure's
# anti-abuse throttle is rate-limiting repeated AI deployments (error 715-123420).
#
# Every `az` call below is scoped to the one resource group named on the command line:
# `az deployment group create` (resource-group scope, never `az deployment sub create`),
# `az acr build` against the registry inside it, `az aks get-credentials` for the cluster
# inside it. Nothing here queries, reads or writes a resource in any other group, and the
# Bicep it deploys cannot reach outside the group either — see the note at the top of
# main.bicep. The group name is also checked against an allow-list, for the same reason
# teardown.sh has one.
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

# Azure CLI on Windows otherwise decodes streamed ACR build logs with the active legacy code
# page. Vite prints a Unicode checkmark on success, which can crash the local CLI while the
# remote build continues. These variables are harmless on Linux and make the exit status reliable.
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8

readonly ALLOWED_GROUPS=("rg-wathiq-dev" "rg-wathiq-test")

readonly RED=$'\033[0;31m'
readonly GREEN=$'\033[0;32m'
readonly YELLOW=$'\033[0;33m'
readonly RESET=$'\033[0m'

die() { echo "${RED}ERROR:${RESET} $*" >&2; exit 1; }
note() { echo; echo "${GREEN}==>${RESET} $*"; }
warn() { echo "${YELLOW}!!${RESET} $*"; }

GROUP="${1:-rg-wathiq-dev}"
LOCATION="${2:-eastus2}"
NAMESPACE="wathiq"
RELEASE="wathiq"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

allowed=false
for candidate in "${ALLOWED_GROUPS[@]}"; do
  [[ "$GROUP" == "$candidate" ]] && allowed=true && break
done
$allowed || die "'$GROUP' is not on the allow-list: ${ALLOWED_GROUPS[*]}"

command -v az >/dev/null || die "the Azure CLI is not installed"
command -v kubectl >/dev/null || die "kubectl is not installed"
az account show >/dev/null 2>&1 || die "not signed in — run 'az login'"

# Helm, from the host if it is there and from a container if it is not. The project rule is
# that tools run in containers rather than being installed on the developer's machine, and a
# chart install needs nothing from the host except the kubeconfig — so mounting that and the
# chart directory is the whole of it.
HELM_IMAGE="alpine/helm:3.16.2"
helm_run() {
  if command -v helm >/dev/null; then
    helm "$@"
  elif command -v docker >/dev/null; then
    # MSYS_NO_PATHCONV stops Git Bash on Windows rewriting the container-side paths.
    MSYS_NO_PATHCONV=1 docker run --rm \
      -v "${HOME}/.kube:/root/.kube" \
      -v "${REPO_ROOT}:/repo" \
      --network host \
      "$HELM_IMAGE" "$@"
  else
    die "neither helm nor docker is available — one of them is needed to install the chart"
  fi
}

# The chart path differs between the two: the host sees the repository, the container /repo.
if command -v helm >/dev/null; then
  CHART_PATH="$REPO_ROOT/infra/helm/wathiq"
else
  CHART_PATH="/repo/infra/helm/wathiq"
fi

SUBSCRIPTION_ID=$(az account show --query id -o tsv)
TENANT_ID=$(az account show --query tenantId -o tsv)
note "Subscription $(az account show --query name -o tsv) ($SUBSCRIPTION_ID)"

# ---------------------------------------------------------------- 0. providers
# Registering a provider is additive and subscription-wide: it makes a resource TYPE available
# and cannot alter any existing resource. Registration is idempotent, so re-running is free.
note "Registering resource providers (additive; no existing resource is affected)..."
for provider in Microsoft.Compute Microsoft.ContainerService Microsoft.Network \
                Microsoft.Storage Microsoft.DBforPostgreSQL Microsoft.MachineLearningServices \
                Microsoft.KeyVault Microsoft.CognitiveServices Microsoft.ContainerRegistry \
                Microsoft.OperationalInsights Microsoft.OperationsManagement \
                Microsoft.Insights Microsoft.Search; do
  state=$(az provider show --namespace "$provider" --query registrationState -o tsv 2>/dev/null || echo "NotRegistered")
  if [[ "$state" != "Registered" ]]; then
    echo "    registering $provider (currently $state)..."
    az provider register --namespace "$provider" --wait
  fi
done

# ---------------------------------------------------------------- 1. group
note "Creating resource group '$GROUP' in $LOCATION..."
az group create --name "$GROUP" --location "$LOCATION" \
  --tags application=wathiq environment=dev managedBy=bicep teardown=allowed \
  --output none
# The tags matter: teardown.sh refuses to delete a group that does not carry both of them.

# ---------------------------------------------------------------- 2. secrets
# Generated here, never committed, and placed straight into Key Vault. The PostgreSQL password
# is passed to the deployment as a secure parameter, which Azure redacts from the deployment
# history.
note "Preparing secrets..."
PG_PASSWORD_FILE="${HOME}/.wathiq-${GROUP}-pg"
if [[ -f "$PG_PASSWORD_FILE" ]]; then
  WATHIQ_PG_PASSWORD=$(cat "$PG_PASSWORD_FILE")
  echo "    reusing the existing database password"
else
  # 32 bytes of base64, then a fixed suffix so it always satisfies Azure's complexity rule.
  WATHIQ_PG_PASSWORD="$(openssl rand -base64 32 | tr -d '/+=' | head -c 28)Aa1!"
  umask 077 && printf '%s' "$WATHIQ_PG_PASSWORD" > "$PG_PASSWORD_FILE"
  echo "    generated a new database password (kept at $PG_PASSWORD_FILE, mode 600)"
fi
export WATHIQ_PG_PASSWORD
JWT_SECRET="$(openssl rand -base64 48 | tr -d '\n')"

# ---------------------------------------------------------------- 3. infrastructure
note "Deploying infrastructure (10-15 minutes; AKS and PostgreSQL are the slow ones)..."
ADMIN_OID=$(az ad signed-in-user show --query id -o tsv 2>/dev/null || echo "")

az deployment group create \
  --resource-group "$GROUP" \
  --name "wathiq-$(date +%Y%m%d-%H%M%S)" \
  --template-file "$REPO_ROOT/infra/bicep/main.bicep" \
  --parameters "$REPO_ROOT/infra/bicep/main.dev.bicepparam" \
  --parameters location="$LOCATION" adminPrincipalId="$ADMIN_OID"   ${WATHIQ_SKIP_AI:+--parameters deployCognitiveServices=false} \
  --output none

note "Reading the deployment outputs..."
outputs=$(az deployment group list --resource-group "$GROUP" \
  --query "sort_by([?properties.provisioningState=='Succeeded'], &properties.timestamp)[-1].properties.outputs" -o json)

get() { echo "$outputs" | python -c "import sys,json;print(json.load(sys.stdin).get('$1',{}).get('value',''))"; }

AKS_NAME=$(get aksName)
REGISTRY_SERVER=$(get registryLoginServer)
REGISTRY_NAME=$(get registryName)
PG_FQDN=$(get postgresFqdn)
PG_DATABASE=$(get postgresDatabase)
PG_USER=$(get postgresAdminUser)
STORAGE_URL=$(get storageAccountUrl)
STORAGE_FS=$(get storageFilesystem)
KEYVAULT_NAME=$(get keyVaultName)
OPENAI_ENDPOINT=$(get openAiEndpoint)
OPENAI_CHAT=$(get openAiChatDeployment)
OPENAI_EMBED=$(get openAiEmbeddingDeployment)
DOCINTEL_ENDPOINT=$(get documentIntelligenceEndpoint)
SAFETY_ENDPOINT=$(get contentSafetyEndpoint)
SEARCH_ENDPOINT=$(get searchEndpoint)
ML_WORKSPACE=$(get machineLearningWorkspace)
APPINSIGHTS_CONNECTION=$(get applicationInsightsConnectionString)
IDENTITY_CLIENT_ID=$(get workloadIdentityClientId)
PUBLIC_DNS_LABEL=$(get publicDnsLabel)
PUBLIC_HOSTNAME=$(get publicHostname)

[[ -n "$AKS_NAME" && -n "$PUBLIC_HOSTNAME" ]] || die "could not read the deployment outputs"

# ---------------------------------------------------------------- 4. key vault
note "Storing secrets in Key Vault '$KEYVAULT_NAME'..."
set_secret() {
  local name="$1"
  local value="$2"
  local attempt
  for attempt in $(seq 1 12); do
    if az keyvault secret set --vault-name "$KEYVAULT_NAME" --name "$name" \
         --value "$value" --output none 2>/dev/null; then
      return 0
    fi
    if [[ "$attempt" -lt 12 ]]; then
      echo "    waiting for Key Vault RBAC propagation ($attempt/12)..."
      sleep 10
    fi
  done
  die "could not store '$name' after waiting for Key Vault RBAC propagation"
}

set_secret postgres-password "$WATHIQ_PG_PASSWORD"
set_secret jwt-secret "$JWT_SECRET"
echo "    postgres-password and jwt-secret stored (these are the only two secrets)"

# ---------------------------------------------------------------- 5. images
# `az acr build` builds in the registry, so nothing large is uploaded from here and no local
# Docker daemon is needed.
note "Building and pushing images in ACR (5-10 minutes)..."
TAG="$(git -C "$REPO_ROOT" rev-parse --short HEAD 2>/dev/null || echo latest)"
if ! git -C "$REPO_ROOT" diff --quiet || ! git -C "$REPO_ROOT" diff --cached --quiet || \
   [[ -n "$(git -C "$REPO_ROOT" ls-files --others --exclude-standard)" ]]; then
  # A moving `-dirty` tag does not change a Deployment's pod template, so Kubernetes would
  # legitimately keep the old image. A timestamp makes every uncommitted deployment traceable
  # and forces the intended rollout; committed builds remain stable by commit SHA.
  TAG="${TAG}-dirty-$(date +%Y%m%d%H%M%S)"
fi

az acr build --registry "$REGISTRY_NAME" --image "wathiq-api:${TAG}" --image "wathiq-api:latest" \
  --file "$REPO_ROOT/backend/Dockerfile" --target prod "$REPO_ROOT/backend" --no-logs --output none
az acr build --registry "$REGISTRY_NAME" --image "wathiq-web:${TAG}" --image "wathiq-web:latest" \
  --file "$REPO_ROOT/frontend/Dockerfile" --target prod "$REPO_ROOT/frontend" --no-logs --output none
az acr build --registry "$REGISTRY_NAME" --image "wathiq-mcp:${TAG}" --image "wathiq-mcp:latest" \
  --file "$REPO_ROOT/mcp_servers/Dockerfile" "$REPO_ROOT/mcp_servers" --no-logs --output none

# ---------------------------------------------------------------- 6. cluster
note "Connecting to AKS '$AKS_NAME'..."
az aks get-credentials --resource-group "$GROUP" --name "$AKS_NAME" --overwrite-existing
kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -

note "Installing the Helm chart..."
helm_run upgrade --install "$RELEASE" "$CHART_PATH" \
  --namespace "$NAMESPACE" \
  --set image.registry="$REGISTRY_SERVER" \
  --set image.tag="$TAG" \
  --set workloadIdentity.clientId="$IDENTITY_CLIENT_ID" \
  --set keyVault.name="$KEYVAULT_NAME" \
  --set keyVault.tenantId="$TENANT_ID" \
  --set postgres.host="$PG_FQDN" \
  --set postgres.database="$PG_DATABASE" \
  --set postgres.user="$PG_USER" \
  --set azure.openAiEndpoint="$OPENAI_ENDPOINT" \
  --set azure.openAiDeployment="$OPENAI_CHAT" \
  --set azure.openAiEmbeddingDeployment="$OPENAI_EMBED" \
  --set azure.docIntelligenceEndpoint="$DOCINTEL_ENDPOINT" \
  --set azure.contentSafetyEndpoint="$SAFETY_ENDPOINT" \
  --set azure.searchEndpoint="$SEARCH_ENDPOINT" \
  --set azure.storageAccountUrl="$STORAGE_URL" \
  --set azure.storageFilesystem="$STORAGE_FS" \
  --set azure.monitorConnectionString="$APPINSIGHTS_CONNECTION" \
  --set azure.mlWorkspace="$ML_WORKSPACE" \
  --set azure.mlResourceGroup="$GROUP" \
  --set azure.mlSubscriptionId="$SUBSCRIPTION_ID" \
  --set web.tls.enabled=true \
  --set web.tls.hostname="$PUBLIC_HOSTNAME" \
  --set web.tls.image="caddy:2.10.2-alpine" \
  --set web.tls.storageSize="1Gi" \
  --set service.azureDnsLabel="$PUBLIC_DNS_LABEL" \
  --wait --wait-for-jobs --timeout 15m

# ---------------------------------------------------------------- done
note "Waiting for the public IP..."
for _ in $(seq 1 30); do
  EXTERNAL_IP=$(kubectl get svc "${RELEASE}-wathiq-web" -n "$NAMESPACE" \
    -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || echo "")
  [[ -n "$EXTERNAL_IP" ]] && break
  sleep 10
done

echo
note "Deployed."
echo "    Wathiq       : https://${PUBLIC_HOSTNAME}/"
echo "    HTTP redirect: http://${EXTERNAL_IP:-<pending>}/"
echo "    Pods         : kubectl get pods -n $NAMESPACE"
echo "    Logs         : kubectl logs -n $NAMESPACE -l app.kubernetes.io/component=api -f"
echo
warn "This is now costing roughly USD 100/month (~USD 3.30/day). When you are finished:"
echo "    ./infra/teardown/teardown.sh $GROUP"

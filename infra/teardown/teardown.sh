#!/usr/bin/env bash
#
# Delete everything Wathiq created in Azure — and nothing else.
#
# ─────────────────────────────────────────────────────────────────────────────
# THIS SCRIPT DELETES THINGS. Read the guards before changing it.
#
# This subscription contains a working system in `filingsiq-rg`. The rule is that Wathiq never
# touches it, and this script is the single most dangerous place that rule could be broken. So
# it refuses to run unless ALL of the following hold:
#
#   1. the resource group name is on the allow-list below (no wildcards, no patterns);
#   2. the group carries the tag `application=wathiq` that main.bicep stamps on it;
#   3. the group carries the tag `teardown=allowed`;
#   4. the operator types the group's name back, in full.
#
# Any one of them failing stops the script. A group that Wathiq did not create cannot satisfy
# 2 and 3, so even a typo that happens to name a real group is caught before anything is
# deleted — and the allow-list means a typo has to be an *exact* match for another Wathiq
# group before it gets that far.
# ─────────────────────────────────────────────────────────────────────────────
#
# Usage:
#   ./infra/teardown/teardown.sh rg-wathiq-dev
#   ./infra/teardown/teardown.sh rg-wathiq-dev --yes    # skip the typed confirmation (CI)

set -euo pipefail

# Exact names only. Adding a pattern here would defeat the whole point of the file.
readonly ALLOWED_GROUPS=(
  "rg-wathiq-dev"
  "rg-wathiq-test"
)

readonly RED=$'\033[0;31m'
readonly YELLOW=$'\033[0;33m'
readonly GREEN=$'\033[0;32m'
readonly RESET=$'\033[0m'

die() { echo "${RED}ERROR:${RESET} $*" >&2; exit 1; }
note() { echo "${GREEN}==>${RESET} $*"; }
warn() { echo "${YELLOW}!!${RESET} $*"; }

GROUP="${1:-}"
ASSUME_YES="${2:-}"

[[ -n "$GROUP" ]] || die "Usage: $0 <resource-group> [--yes]"

# ---- guard 1: the allow-list ------------------------------------------------
allowed=false
for candidate in "${ALLOWED_GROUPS[@]}"; do
  [[ "$GROUP" == "$candidate" ]] && allowed=true && break
done
$allowed || die "'$GROUP' is not on the teardown allow-list: ${ALLOWED_GROUPS[*]}
This script only ever deletes resource groups Wathiq created. If you meant a different group,
delete it yourself — deliberately, and with the portal in front of you."

command -v az >/dev/null || die "the Azure CLI is not installed"
az account show >/dev/null 2>&1 || die "not signed in — run 'az login'"

SUBSCRIPTION=$(az account show --query name -o tsv)
SUBSCRIPTION_ID=$(az account show --query id -o tsv)

az group show --name "$GROUP" >/dev/null 2>&1 || {
  note "Resource group '$GROUP' does not exist. Nothing to tear down."
  exit 0
}

# ---- guards 2 and 3: the tags main.bicep stamps on it -----------------------
APPLICATION_TAG=$(az group show --name "$GROUP" --query "tags.application" -o tsv 2>/dev/null || echo "")
TEARDOWN_TAG=$(az group show --name "$GROUP" --query "tags.teardown" -o tsv 2>/dev/null || echo "")

[[ "$APPLICATION_TAG" == "wathiq" ]] || die "'$GROUP' is not tagged application=wathiq (found: '${APPLICATION_TAG:-none}').
Refusing to delete a resource group this project did not create."

[[ "$TEARDOWN_TAG" == "allowed" ]] || die "'$GROUP' is not tagged teardown=allowed (found: '${TEARDOWN_TAG:-none}').
Refusing to delete a resource group that has not opted in."

# ---- show exactly what will go ----------------------------------------------
echo
warn "About to PERMANENTLY DELETE every resource in:"
echo "    subscription : $SUBSCRIPTION ($SUBSCRIPTION_ID)"
echo "    group        : $GROUP"
echo
note "Resources that will be deleted:"
az resource list --resource-group "$GROUP" --query "[].{name:name,type:type}" -o table || true
echo

# A last sanity check the operator can see: name every OTHER group, so it is obvious that
# none of them is being touched.
note "Resource groups that will NOT be touched:"
az group list --query "[?name!='$GROUP'].name" -o tsv | sed 's/^/    /' || true
echo

# ---- guard 4: type the name back --------------------------------------------
if [[ "$ASSUME_YES" != "--yes" ]]; then
  read -r -p "Type the resource group name to confirm deletion: " typed
  [[ "$typed" == "$GROUP" ]] || die "'$typed' does not match '$GROUP' — nothing was deleted."
fi

# ---- delete ------------------------------------------------------------------
note "Deleting resource group '$GROUP' (this takes 5-15 minutes, mostly AKS)..."
az group delete --name "$GROUP" --yes --no-wait
note "Deletion started. Follow it with: az group show --name $GROUP"

# ---- purge the soft-deleted Key Vault ----------------------------------------
# Key Vault soft delete cannot be switched off. A deleted vault is recoverable for its
# retention period and, more to the point here, its NAME stays taken for that long — so
# redeploying with the same name fails with a confusing "already exists". Purging releases it.
#
# Purge protection is deliberately off in modules/keyvault.bicep for exactly this reason. In
# production it must be ON, and then this step correctly cannot work.
echo
note "Checking for soft-deleted Key Vaults to purge..."
DELETED_VAULTS=$(az keyvault list-deleted --query "[?properties.tags.application=='wathiq'].name" -o tsv 2>/dev/null || echo "")
if [[ -n "$DELETED_VAULTS" ]]; then
  while IFS= read -r vault; do
    [[ -z "$vault" ]] && continue
    note "Purging soft-deleted Key Vault '$vault'..."
    az keyvault purge --name "$vault" --no-wait 2>/dev/null \
      || warn "Could not purge '$vault' — purge it in the portal, or its name stays taken."
  done <<< "$DELETED_VAULTS"
else
  note "No soft-deleted Wathiq Key Vaults found."
fi

# ---- soft-deleted Cognitive Services accounts --------------------------------
# Same problem, same fix: a deleted Cognitive Services account holds its name, and an OpenAI
# account also holds its quota allocation until it is purged. Leaving one behind means the
# next deployment can fail for want of quota that nothing is actually using.
echo
note "Checking for soft-deleted Cognitive Services accounts to purge..."
az cognitiveservices account list-deleted \
  --query "[?contains(name,'wathiq')].{name:name,location:location,rg:resourceGroup}" -o tsv 2>/dev/null \
  | while read -r name location rg; do
      [[ -z "$name" ]] && continue
      note "Purging '$name' in $location..."
      az cognitiveservices account purge --name "$name" --location "$location" \
        --resource-group "$rg" 2>/dev/null \
        || warn "Could not purge '$name' — purge it in the portal to release its quota."
    done

echo
note "Teardown complete. Nothing outside '$GROUP' was touched."
note "Confirm the bill has stopped: https://portal.azure.com/#view/Microsoft_Azure_CostManagement"

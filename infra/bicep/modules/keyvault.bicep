// Key Vault: the only place a Wathiq secret is allowed to live.
//
// Two decisions worth knowing about:
//
// **RBAC, not access policies.** Access policies are the older model: a list on the vault
// saying which object id may do what. They cannot be assigned at the level of an individual
// secret, they are invisible to `az role assignment list`, and they are one more thing to audit
// separately. RBAC puts vault permissions in the same place as every other permission in the
// subscription.
//
// **Soft delete is on and cannot be turned off** (Azure stopped allowing it). That matters for
// teardown: a deleted vault is recoverable for `softDeleteRetentionInDays`, and its *name*
// stays taken for that long. `infra/teardown/teardown.sh` purges it explicitly, otherwise
// redeploying with the same name fails with a confusing "already exists".
//
// Purge protection is deliberately OFF here. In production it must be on — it stops an
// attacker permanently destroying your secrets. In a demo resource group it would mean the
// vault genuinely cannot be removed for 90 days, so teardown could not do its job.

param location string
param name string
param tags object

@description('Object id of the human running the deployment, who must create the two application secrets. Empty grants nobody.')
param adminPrincipalId string = ''

// Built-in role: Key Vault Secrets Officer. It can manage secret values, but cannot change the
// vault or its role assignments. `deploy.sh` needs this to create postgres-password and
// jwt-secret after the vault exists; the read-only Secrets User role is insufficient.
var secretsOfficerRoleId = 'b86a8fe4-44ce-4948-aee5-eccb2c155cd7'

resource vault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: name
  location: location
  tags: tags
  properties: {
    sku: {
      family: 'A'
      name: 'standard'
    }
    tenantId: subscription().tenantId
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 7
    // See the note above: on in production, off here so the group can actually be torn down.
    enablePurgeProtection: null
    publicNetworkAccess: 'Enabled'
    networkAcls: {
      defaultAction: 'Allow'
      bypass: 'AzureServices'
    }
  }
}

resource adminAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(adminPrincipalId)) {
  // A deterministic GUID: the same inputs always produce the same assignment name, so a
  // redeploy updates it instead of failing with "role assignment already exists".
  name: guid(vault.id, adminPrincipalId, secretsOfficerRoleId)
  scope: vault
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', secretsOfficerRoleId)
    principalId: adminPrincipalId
    principalType: 'User'
  }
}

output id string = vault.id
output name string = vault.name
output uri string = vault.properties.vaultUri

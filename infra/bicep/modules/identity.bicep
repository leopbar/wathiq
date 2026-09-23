// The identity Wathiq's pods run as, and everything it is allowed to do.
//
// This is the security model in one file. A pod presents its Kubernetes service-account token;
// AKS's OIDC issuer vouches for it; Entra trades it for a real Azure token for the
// user-assigned identity below. No key, no connection string, no secret in a manifest — which
// is why `app/azure/credentials.py` prefers `DefaultAzureCredential` everywhere and why the
// Key Vault mount in the Helm chart carries so little.
//
// **Least privilege, and each grant says why.** The same principle the MCP servers enforce for
// tools — one server per capability, an allow-list per graph node — applied to Azure. The
// identity can read models and documents; it cannot create a model deployment, empty a
// container or read a Key Vault's access policies.
//
// A `guid(scope, principal, role)` assignment name is deterministic, so redeploying updates
// the assignment rather than failing with "role assignment already exists".

param location string
param name string
param tags object

@description('The AKS cluster OIDC issuer URL — the thing Entra is told to trust.')
param oidcIssuerUrl string

@description('The kubelet identity, which is what actually pulls images. Not the workload identity.')
param kubeletPrincipalId string

param registryId string
param storageAccountId string
param keyVaultId string
param openAiId string
param documentIntelligenceId string
param contentSafetyId string
@description('Empty when AI Search was not deployed.')
param searchId string = ''

@description('Kubernetes namespace and service account the federation trusts. Must match the Helm chart.')
param kubernetesNamespace string = 'wathiq'
param kubernetesServiceAccount string = 'wathiq'

// ---- built-in role definition ids ------------------------------------------
// Ids, not names: a role's display name can be localised, an id cannot.
var roles = {
  // Call a model deployment. NOT "Cognitive Services Contributor", which could create and
  // delete deployments — and so could run up a bill or delete the model mid-case.
  openAiUser: '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'
  // Call Document Intelligence and Content Safety. Read-only against the service.
  cognitiveServicesUser: 'a97b65f3-24c7-4388-baec-2e87135dc908'
  // Read and write blobs. Wathiq stores uploaded documents, so read alone is not enough.
  storageBlobDataContributor: 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
  // Ask for a user delegation key — what signs the viewer's SAS links. Without this the SAS
  // path in `app/azure/adls.py` silently falls back to streaming bytes through the API, which
  // works but is the slower path, and the cause is not obvious.
  storageBlobDelegator: 'db58b8e5-c6ad-4a2a-8342-4190687cbf4a'
  // Read secret values. NOT "Key Vault Administrator": the app reads secrets, it never writes
  // them or changes who else can.
  keyVaultSecretsUser: '4633458b-17de-408a-b874-0445c86b69e6'
  // Query the policy index. Read-only: the index is built by the deploy script, not by a pod
  // serving traffic.
  searchIndexDataReader: '1407120a-92aa-4202-b7e9-c0e197c71c8f'
  // Pull images. Held by the kubelet identity, not the workload identity.
  acrPull: '7f951dda-4ed3-4680-a7ca-43fe172d538d'
}

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: name
  location: location
  tags: tags
}

// The federation: "a token from THIS cluster, for THIS namespace and service account, may act
// as this identity". All three parts are checked, so a pod in another namespace on the same
// cluster cannot use it.
resource federation 'Microsoft.ManagedIdentity/userAssignedIdentities/federatedIdentityCredentials@2023-01-31' = {
  parent: identity
  name: 'wathiq-aks-federation'
  properties: {
    issuer: oidcIssuerUrl
    subject: 'system:serviceaccount:${kubernetesNamespace}:${kubernetesServiceAccount}'
    audiences: [
      'api://AzureADTokenExchange'
    ]
  }
}

// ---- existing resources, referenced so a role can be scoped to them ---------

resource registry 'Microsoft.ContainerRegistry/registries@2023-11-01-preview' existing = {
  name: last(split(registryId, '/'))
}

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' existing = {
  name: last(split(storageAccountId, '/'))
}

resource vault 'Microsoft.KeyVault/vaults@2023-07-01' existing = {
  name: last(split(keyVaultId, '/'))
}

resource openAi 'Microsoft.CognitiveServices/accounts@2024-10-01' existing = {
  name: last(split(openAiId, '/'))
}

resource documentIntelligence 'Microsoft.CognitiveServices/accounts@2024-10-01' existing = {
  name: last(split(documentIntelligenceId, '/'))
}

resource contentSafety 'Microsoft.CognitiveServices/accounts@2024-10-01' existing = {
  name: last(split(contentSafetyId, '/'))
}

resource searchService 'Microsoft.Search/searchServices@2024-06-01-preview' existing = if (!empty(searchId)) {
  name: empty(searchId) ? 'placeholder' : last(split(searchId, '/'))
}

// ---- role assignments -------------------------------------------------------

resource openAiAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(openAiId, identity.id, roles.openAiUser)
  scope: openAi
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.openAiUser)
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource documentIntelligenceAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(documentIntelligenceId, identity.id, roles.cognitiveServicesUser)
  scope: documentIntelligence
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.cognitiveServicesUser)
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource contentSafetyAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(contentSafetyId, identity.id, roles.cognitiveServicesUser)
  scope: contentSafety
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.cognitiveServicesUser)
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource storageAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccountId, identity.id, roles.storageBlobDataContributor)
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.storageBlobDataContributor)
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource storageDelegatorAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccountId, identity.id, roles.storageBlobDelegator)
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.storageBlobDelegator)
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource keyVaultAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVaultId, identity.id, roles.keyVaultSecretsUser)
  scope: vault
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.keyVaultSecretsUser)
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource searchAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(searchId)) {
  name: guid(empty(searchId) ? resourceGroup().id : searchId, identity.id, roles.searchIndexDataReader)
  scope: searchService
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.searchIndexDataReader)
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

// Image pulls. Granted to the KUBELET identity — a common hour-long confusion is granting
// AcrPull to the workload identity and watching every pod sit in ImagePullBackOff.
resource acrPullAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(registryId, kubeletPrincipalId, roles.acrPull)
  scope: registry
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.acrPull)
    principalId: kubeletPrincipalId
    principalType: 'ServicePrincipal'
  }
}

output id string = identity.id
output name string = identity.name
@description('Goes on the Kubernetes service account as azure.workload.identity/client-id.')
output clientId string = identity.properties.clientId
output principalId string = identity.properties.principalId
output federationSubject string = federation.properties.subject

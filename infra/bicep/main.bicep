// Wathiq — every Azure resource, in one resource group.
//
// ─────────────────────────────────────────────────────────────────────────────
// SCOPE IS THE SAFETY PROPERTY. Read this before changing anything.
//
// This template deploys at RESOURCE GROUP scope, not subscription scope. That is deliberate
// and it is load-bearing: a resource-group deployment physically cannot create, modify or
// delete anything outside the group it is given. This subscription contains a working system
// in `filingsiq-rg`, and the rule for Wathiq is that it never touches it. Scope is how that
// rule is enforced by Azure rather than by someone remembering it.
//
// So: no `targetScope = 'subscription'`, no resource group creation in here, and no role
// assignment whose scope is anything but a resource declared in this file.
// ─────────────────────────────────────────────────────────────────────────────
//
// Deploy:
//   az deployment group create -g rg-wathiq-dev -f infra/bicep/main.bicep \
//      -p @infra/bicep/main.dev.bicepparam
//
// Everything is sized for a demo: the smallest SKU that actually works, free tiers wherever
// this subscription still has one. `infra/README.md` carries the costed list.

targetScope = 'resourceGroup'

// ---------------------------------------------------------------- parameters

@description('Azure region. Keep every resource in one region — cross-region traffic is billed and slower.')
param location string = resourceGroup().location

@description('Prefix for every resource name. Short: some resource types cap names at 24 characters.')
@minLength(3)
@maxLength(12)
param namePrefix string = 'wathiq'

@description('Environment tag and name suffix.')
@allowed(['dev', 'test', 'prod'])
param environment string = 'dev'

@description('PostgreSQL administrator login.')
param postgresAdminUser string = 'wathiq'

@description('PostgreSQL administrator password. Never hard-coded, never committed — pass it at deploy time or read it from Key Vault.')
@secure()
@minLength(12)
param postgresAdminPassword string

@description('AKS node size. TWO separate checks decide this, and a size has to pass both: it must be offered to the subscription in the region (preflight refuses the rest), and its VM FAMILY must have vCPU quota left. A B-series size failed the first check here and a B-series v2 size failed the second. Standard_D2s_v3 (2 vCPU / 8 GiB) passes both. Check with: az vm list-usage -l <region> -o json')
param aksNodeSize string = 'Standard_D2s_v3'

@description('AKS node count. One is enough for a demo; the cluster autoscaler is off so the bill is predictable.')
@minValue(1)
@maxValue(5)
param aksNodeCount int = 1

@description('Chat model deployment. gpt-4.1-mini draws on a DIFFERENT subscription quota pool than the gpt-4o this subscription already uses, so deploying it cannot throttle anything already running. Check headroom with: az cognitiveservices usage list -l <region> -o table')
param chatModelName string = 'gpt-4.1-mini'
param chatModelVersion string = '2025-04-14'

@description('Capacity in thousands of tokens per minute.')
@minValue(1)
param chatModelCapacity int = 30

@description('Embedding model deployment. Standard (not GlobalStandard) for the same quota-pool reason.')
param embeddingModelName string = 'text-embedding-3-small'
param embeddingModelVersion string = '1'
@minValue(1)
param embeddingModelCapacity int = 30

@description('Deploy Azure AI Search. OFF by default: the free tier in this subscription is already taken by another system, so turning this on means paying about USD 74/month for a Basic service to do what the pgvector retriever already does. The adapter is written and tested either way.')
param deployAiSearch bool = false

@description('Deploy an Azure ML workspace. The workspace itself is free and is also an MLflow server, so this is worth having on its own.')
param deployMachineLearning bool = true

@description('Also create the compute cluster the calibration job runs on. OFF by default: a new subscription often has a total AmlCompute vCPU quota of ZERO, and the cluster is then refused with ClusterMinNodesExceedCoreQuota. Raising it is a support request, not a template change. With this off the workspace still deploys and MLflow tracking still works; only job submission needs the quota.')
param deployMachineLearningCompute bool = false

@description('Create or update the Cognitive Services accounts (Foundry, Document Intelligence, Content Safety) and the model deployments. Set FALSE to leave already-deployed AI services completely untouched and deploy only the rest; the endpoints are then read from the existing resources, so every output still resolves. Two real reasons to want it: iterating on the cluster without re-declaring model deployments, and getting past the anti-abuse throttle that rate-limits repeated Cognitive Services deployments (error 715-123420, unusual activity for your account) and blocks the whole template while it lasts.')
param deployCognitiveServices bool = true

@description('Object id of the human running the deployment. Grants secret-value management (not vault or RBAC management) so deploy.sh can create the two application secrets. Leave empty to grant nobody — the workload identity below is granted separately.')
param adminPrincipalId string = ''

// ---------------------------------------------------------------- naming
// `uniqueString` on the resource group id gives a stable, deterministic suffix: the same
// resource group always produces the same names, so a redeploy updates rather than duplicates,
// while two different groups never collide on a globally unique name.

var suffix = uniqueString(resourceGroup().id)
var baseName = '${namePrefix}-${environment}'

// Storage accounts and registries: lowercase alphanumeric only, and short.
var storageAccountName = toLower('${namePrefix}st${suffix}')
var registryName = toLower('${namePrefix}cr${suffix}')

var tags = {
  application: 'wathiq'
  environment: environment
  managedBy: 'bicep'
  // Read by `infra/teardown/teardown.sh`, which refuses to delete anything without it.
  teardown: 'allowed'
}

// ---------------------------------------------------------------- modules

module monitoring 'modules/monitoring.bicep' = {
  name: 'monitoring'
  params: {
    location: location
    baseName: baseName
    tags: tags
  }
}

module keyvault 'modules/keyvault.bicep' = {
  name: 'keyvault'
  params: {
    location: location
    name: take('${namePrefix}kv${suffix}', 24)
    tags: tags
    adminPrincipalId: adminPrincipalId
  }
}

module registry 'modules/registry.bicep' = {
  name: 'registry'
  params: {
    location: location
    name: registryName
    tags: tags
  }
}

module storage 'modules/storage.bicep' = {
  name: 'storage'
  params: {
    location: location
    name: storageAccountName
    tags: tags
    // The hierarchical namespace is what makes this ADLS Gen2 rather than plain blob storage.
    enableHierarchicalNamespace: true
  }
}

// A second, plain storage account, for the Azure ML workspace only.
//
// Not a duplication anyone chose: an Azure ML workspace **refuses** a storage account with a
// hierarchical namespace ("Cannot use storage with HNS enabled"), and Wathiq's documents need
// one. The two requirements are incompatible, so they get an account each. Two nearly-empty
// LRS accounts cost about the same as one, and the alternative — dropping HNS to share — would
// give up the per-case ACL that was the reason to pick ADLS Gen2 in the first place.
module mlStorage 'modules/storage.bicep' = if (deployMachineLearning) {
  name: 'mlStorage'
  params: {
    location: location
    name: toLower('${namePrefix}ml${suffix}')
    tags: tags
    enableHierarchicalNamespace: false
    // The workspace creates the containers it wants.
    createDocumentsContainer: false
  }
}

module postgres 'modules/postgres.bicep' = {
  name: 'postgres'
  params: {
    location: location
    name: '${baseName}-pg-${suffix}'
    tags: tags
    adminUser: postgresAdminUser
    adminPassword: postgresAdminPassword
  }
}

module openai 'modules/openai.bicep' = if (deployCognitiveServices) {
  name: 'openai'
  params: {
    location: location
    name: '${baseName}-openai'
    tags: tags
    chatModelName: chatModelName
    chatModelVersion: chatModelVersion
    chatModelCapacity: chatModelCapacity
    embeddingModelName: embeddingModelName
    embeddingModelVersion: embeddingModelVersion
    embeddingModelCapacity: embeddingModelCapacity
  }
}

module documentIntelligence 'modules/cognitive.bicep' = if (deployCognitiveServices) {
  name: 'documentIntelligence'
  params: {
    location: location
    name: '${baseName}-docintel'
    tags: tags
    kind: 'FormRecognizer'
    // F0 is the free tier: 500 pages a month. Still available in this subscription because
    // the existing Document Intelligence account is S0.
    skuName: 'F0'
  }
}

module contentSafety 'modules/cognitive.bicep' = if (deployCognitiveServices) {
  name: 'contentSafety'
  params: {
    location: location
    name: '${baseName}-safety'
    tags: tags
    kind: 'ContentSafety'
    // S0, not F0: this subscription's one free Content Safety account is already in use by
    // another system, and taking it would break that system. S0 is pay-per-call and costs
    // roughly nothing at demo volume.
    skuName: 'S0'
  }
}

module search 'modules/search.bicep' = if (deployAiSearch) {
  name: 'search'
  params: {
    location: location
    name: '${baseName}-search'
    tags: tags
  }
}

module machineLearning 'modules/machinelearning.bicep' = if (deployMachineLearning) {
  name: 'machineLearning'
  params: {
    location: location
    name: '${baseName}-ml'
    tags: tags
    // The plain account, not the ADLS one — see the note on `mlStorage` above.
    storageAccountId: mlStorage!.outputs.id
    keyVaultId: keyvault.outputs.id
    applicationInsightsId: monitoring.outputs.applicationInsightsId
    deployCompute: deployMachineLearningCompute
  }
}

// When the modules above are skipped, the endpoints are read from the resources that are
// already there. `existing` does not create or modify anything — it is a lookup — so this path
// cannot trigger the throttle it exists to avoid.
resource existingOpenAi 'Microsoft.CognitiveServices/accounts@2024-10-01' existing = if (!deployCognitiveServices) {
  name: '${baseName}-openai'
}

resource existingDocIntelligence 'Microsoft.CognitiveServices/accounts@2024-10-01' existing = if (!deployCognitiveServices) {
  name: '${baseName}-docintel'
}

resource existingContentSafety 'Microsoft.CognitiveServices/accounts@2024-10-01' existing = if (!deployCognitiveServices) {
  name: '${baseName}-safety'
}

// One place each answer comes from, whichever branch produced it.
//
// A note for anyone changing these. Bicep compiles each one to
// `if(deployCognitiveServices, reference(<the module>), reference(<the existing account>))`, and
// ARM's `if()` does **not** reliably short-circuit. That is safe here only because the account
// exists in both configurations by the time outputs are evaluated: the module creates it when
// the flag is on, and it is already there when the flag is off. Adding a branch that references
// a resource which might not exist at all would break the other path — which is a genuinely
// confusing failure, because the branch that breaks is the one you did not take.
var openAiId = deployCognitiveServices ? openai!.outputs.id : existingOpenAi!.id
var openAiEndpoint = deployCognitiveServices ? openai!.outputs.endpoint : existingOpenAi!.properties.endpoint
var docIntelligenceId = deployCognitiveServices ? documentIntelligence!.outputs.id : existingDocIntelligence!.id
var docIntelligenceEndpoint = deployCognitiveServices ? documentIntelligence!.outputs.endpoint : existingDocIntelligence!.properties.endpoint
var contentSafetyId = deployCognitiveServices ? contentSafety!.outputs.id : existingContentSafety!.id
var contentSafetyEndpoint = deployCognitiveServices ? contentSafety!.outputs.endpoint : existingContentSafety!.properties.endpoint

module aks 'modules/aks.bicep' = {
  name: 'aks'
  params: {
    location: location
    name: '${baseName}-aks'
    tags: tags
    nodeSize: aksNodeSize
    nodeCount: aksNodeCount
    logAnalyticsWorkspaceId: monitoring.outputs.logAnalyticsWorkspaceId
  }
}

// The identity the pods run as, and every role it needs. Kept in one module so "what can
// Wathiq do in Azure" is one file rather than a hunt through nine.
module identity 'modules/identity.bicep' = {
  name: 'identity'
  params: {
    location: location
    name: '${baseName}-id'
    tags: tags
    oidcIssuerUrl: aks.outputs.oidcIssuerUrl
    kubeletPrincipalId: aks.outputs.kubeletPrincipalId
    registryId: registry.outputs.id
    storageAccountId: storage.outputs.id
    keyVaultId: keyvault.outputs.id
    openAiId: openAiId
    documentIntelligenceId: docIntelligenceId
    contentSafetyId: contentSafetyId
    searchId: deployAiSearch ? search!.outputs.id : ''
  }
}

// ---------------------------------------------------------------- outputs
// These are what `infra/scripts/deploy.sh` turns into the Helm values and the `.env`. No
// secret is output: every one of them is an endpoint, a name or a client id.

output resourceGroupName string = resourceGroup().name
output location string = location
output publicDnsLabel string = '${baseName}-${suffix}'
output publicHostname string = '${baseName}-${suffix}.${location}.cloudapp.azure.com'

output aksName string = aks.outputs.name
output registryLoginServer string = registry.outputs.loginServer
output registryName string = registry.outputs.name

output postgresFqdn string = postgres.outputs.fqdn
output postgresDatabase string = postgres.outputs.databaseName
output postgresAdminUser string = postgresAdminUser

output storageAccountUrl string = storage.outputs.dfsEndpoint
output storageFilesystem string = storage.outputs.filesystemName

output keyVaultName string = keyvault.outputs.name
output keyVaultUri string = keyvault.outputs.uri

output openAiEndpoint string = openAiEndpoint
// The deployment names are the parameters either way: when the module is skipped, these are the
// names it would have created, which are the names already there.
output openAiChatDeployment string = chatModelName
output openAiEmbeddingDeployment string = embeddingModelName

output documentIntelligenceEndpoint string = docIntelligenceEndpoint
output contentSafetyEndpoint string = contentSafetyEndpoint

output searchEndpoint string = deployAiSearch ? search!.outputs.endpoint : ''
output searchDeployed bool = deployAiSearch

output machineLearningWorkspace string = deployMachineLearning ? machineLearning!.outputs.name : ''

output applicationInsightsConnectionString string = monitoring.outputs.connectionString

output workloadIdentityClientId string = identity.outputs.clientId
output workloadIdentityName string = identity.outputs.name

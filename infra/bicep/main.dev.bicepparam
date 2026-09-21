// Parameters for the demo deployment.
//
//   az deployment group create -g rg-wathiq-dev \
//      -f infra/bicep/main.bicep -p infra/bicep/main.dev.bicepparam
//
// The PostgreSQL password is NOT here. It is read from the environment at deploy time, so this
// file is safe to commit and `gitleaks` has nothing to find. `infra/scripts/deploy.sh`
// generates a strong one on first deploy and puts it straight into Key Vault.

using './main.bicep'

param namePrefix = 'wathiq'
param environment = 'dev'
param location = 'eastus2'

// Read from the environment — never written down here.
param postgresAdminPassword = readEnvironmentVariable('WATHIQ_PG_PASSWORD')

// One node, carrying api + worker + web + four MCP servers. That fits on a single small
// machine because M4's in-process workflow engine runs the same steps as Conductor without a
// separate orchestrator. See modules/aks.bicep.
//
// Getting here took three attempts, and the reason is worth keeping: a VM size has to pass
// TWO independent checks, and the error messages for them look nothing alike.
//
//   Standard_B2s      refused — not offered to this subscription in eastus2 at all
//                     ("The VM size of Standard_B2s is not allowed in your subscription")
//   Standard_B2ls_v2  offered, but the standardBsv2Family vCPU quota is 0
//                     ("Insufficient vcpu quota requested 2, remaining 0")
//   Standard_D2s_v3   offered AND the DSv3 family has 10 vCPU free  <- this one
//
// D2s_v3 is 2 vCPU / 8 GiB at about USD 0.096/hour (~USD 70/month), against the ~USD 30/month
// a B-series would have cost. Since the group is torn down after verification, the difference
// over a day or two is a couple of dollars — and 8 GiB gives the seven workloads real headroom
// instead of the 4 GiB the original sizing assumed.
param aksNodeSize = 'Standard_D2s_v3'
param aksNodeCount = 1

// gpt-4.1-mini on the Standard SKU.
//
// Two constraints decided this, in order. First, it has to be a model Azure will still deploy:
// gpt-4o-mini 2024-07-18 was the obvious choice and the deployment preflight refused it as
// deprecated, even though `az cognitiveservices model list` still advertises it. Second, and the
// one that matters more here, it has to sit on a quota pool the subscription's other system does
// not use. Measured before choosing:
//
//   OpenAI.Standard.gpt-4o          10 / 50    <- in use by the other system
//   OpenAI.Standard.gpt4.1-mini      0 / 200   <- Wathiq
//
// Different pools, so nothing Wathiq does can throttle it. See modules/openai.bicep.
param chatModelName = 'gpt-4.1-mini'
param chatModelVersion = '2025-04-14'
param chatModelCapacity = 30

param embeddingModelName = 'text-embedding-3-small'
param embeddingModelVersion = '1'
param embeddingModelCapacity = 30

// Off: the free AI Search tier in this subscription is already taken, and a Basic service
// would be about USD 74/month to replace a pgvector retriever that already works. The adapter
// in app/azure/search.py is written and tested regardless.
param deployAiSearch = false

param deployMachineLearning = true

// The compute cluster stays off: this subscription's total AmlCompute vCPU quota is 0, so
// creating one is refused and would fail the whole deployment. The workspace still deploys and
// still serves as an MLflow endpoint; submitting a calibration job is what needs the quota.
param deployMachineLearningCompute = false

// Set to your own object id (`az ad signed-in-user show --query id -o tsv`) to be able to read
// the vault's secrets yourself. Empty grants nobody, which is the safe default.
param adminPrincipalId = ''

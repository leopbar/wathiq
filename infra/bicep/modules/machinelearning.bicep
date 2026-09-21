// Azure ML workspace — where the calibration fit runs as a recorded job.
//
// The workspace itself is free; you pay for compute while it runs. The compute cluster below
// has `minNodeCount: 0`, so it scales to nothing when idle and a fit that takes ten seconds
// costs about a cent. That is the whole reason this is affordable in a demo.
//
// A workspace requires a storage account, a Key Vault and an Application Insights instance.
// They are passed in rather than created here, so Wathiq has exactly one of each — the ML
// workspace's documents land in the same account as everything else, and its traces in the
// same Application Insights.

param location string
param name string
param tags object
param storageAccountId string
param keyVaultId string
param applicationInsightsId string

@description('Compute cluster name. Must match WATHIQ_AZURE_ML_COMPUTE.')
param computeName string = 'wathiq-cpu'

@description('Cluster node size. The fit is a few hundred floating-point operations; the smallest node is generous.')
param computeSize string = 'Standard_DS2_v2'

@description('Create the compute cluster. Off by default — see the note below.')
param deployCompute bool = false

resource workspace 'Microsoft.MachineLearningServices/workspaces@2024-10-01' = {
  name: name
  location: location
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    friendlyName: 'Wathiq calibration'
    description: 'Fits and records the per-field confidence calibration curve.'
    storageAccount: storageAccountId
    keyVault: keyVaultId
    applicationInsights: applicationInsightsId
    publicNetworkAccess: 'Enabled'
  }
}

// The compute cluster, and why it is opt-in.
//
// AmlCompute draws on its own subscription vCPU quota, separate from the VM quota AKS uses, and
// a subscription that has never run an ML job often has a total of **zero**. The cluster is then
// refused outright with `ClusterMinNodesExceedCoreQuota` — which fails the whole deployment for
// a resource the demo does not need to stand up.
//
// Raising that quota is a support request with a human on the other end, not something a
// template can do. So the default is off: the workspace deploys (it is free, and it is itself an
// MLflow server, so M5's tracking works against it), and only *submitting a job* needs the
// quota. `app/azure/ml.py` reports the failure honestly rather than pretending a fit ran.
resource compute 'Microsoft.MachineLearningServices/workspaces/computes@2024-10-01' = if (deployCompute) {
  parent: workspace
  name: computeName
  location: location
  properties: {
    computeType: 'AmlCompute'
    properties: {
      vmSize: computeSize
      // Low priority: a calibration fit is interruptible, and this is roughly a fifth of the
      // dedicated price. If it is evicted the job is resubmitted; nothing is waiting on it
      // that a person would notice.
      vmPriority: 'LowPriority'
      scaleSettings: {
        // Zero minimum is what makes an idle workspace free.
        minNodeCount: 0
        maxNodeCount: 1
        // Give the node back two minutes after the job ends.
        nodeIdleTimeBeforeScaleDown: 'PT2M'
      }
    }
  }
}

output id string = workspace.id
output name string = workspace.name
output computeName string = deployCompute ? compute!.name : ''
@description('The workspace is itself an MLflow server; pointing WATHIQ_MLFLOW_TRACKING_URI here moves M5 tracking into Azure with no code change.')
output mlflowTrackingUri string = workspace.properties.mlFlowTrackingUri

// AKS — the cluster the whole stack runs on.
//
// **Why one small node is enough.** M4 built a second workflow engine: an in-process runner
// implementing the same `ProcessEngine` interface as Conductor, for a machine without 2 GB to
// spare. That decision pays off here. With `WATHIQ_PROCESS_ENGINE=inprocess` the cluster runs
// api + worker + web + four MCP servers in about 1.2 GiB, which fits beside the ~1 GiB of
// system pods on a 4 GiB node. Running Conductor instead would need a second node and roughly
// double the compute bill.
//
// **Free control plane.** The `Free` SKU tier has no SLA on the API server; `Standard` costs
// about USD 73/month for one. A demo does not need an SLA on its control plane.
//
// **Workload identity, not secrets.** `oidcIssuerProfile` and `workloadIdentity` together let
// a pod exchange a Kubernetes service-account token for an Entra token. That is what lets
// every Azure adapter authenticate with no key stored anywhere — see `identity.bicep` for the
// federation and the roles.

param location string
param name string
param tags object
param nodeSize string
param nodeCount int
param logAnalyticsWorkspaceId string

@description('Kubernetes version. Pinned: an automatic upgrade that changes the API version under a running demo is not a surprise anyone wants. Must be on the standard support plan — an out-of-support version is refused at create time unless the cluster is enrolled in Long-Term Support. Check with: az aks get-versions -l <region> -o table')
param kubernetesVersion string = '1.34'

resource cluster 'Microsoft.ContainerService/managedClusters@2024-09-01' = {
  name: name
  location: location
  tags: tags
  sku: {
    name: 'Base'
    tier: 'Free'
  }
  identity: {
    // The cluster's own identity, used to manage its node resource group. Distinct from the
    // workload identity the pods use.
    type: 'SystemAssigned'
  }
  properties: {
    dnsPrefix: name
    kubernetesVersion: kubernetesVersion
    enableRBAC: true

    // The two halves of workload identity.
    oidcIssuerProfile: {
      enabled: true
    }
    securityProfile: {
      workloadIdentity: {
        enabled: true
      }
    }

    agentPoolProfiles: [
      {
        name: 'system'
        mode: 'System'
        count: nodeCount
        vmSize: nodeSize
        osType: 'Linux'
        osSKU: 'Ubuntu'
        // 32 GiB is the smallest managed disk AKS accepts and is ample: the images live in
        // ACR and nothing is written to the node.
        osDiskSizeGB: 32
        osDiskType: 'Managed'
        type: 'VirtualMachineScaleSets'
        // Autoscaling deliberately off. A demo with an unpredictable node count is a demo with
        // an unpredictable bill.
        enableAutoScaling: false
        maxPods: 60
      }
    ]

    networkProfile: {
      // `overlay` keeps pod IPs off the VNet address space, so the cluster does not need a
      // large subnet planned in advance.
      networkPlugin: 'azure'
      networkPluginMode: 'overlay'
      networkPolicy: 'cilium'
      networkDataplane: 'cilium'
      loadBalancerSku: 'standard'
      serviceCidr: '10.10.0.0/16'
      dnsServiceIP: '10.10.0.10'
    }

    addonProfiles: {
      // Container insights into the same Log Analytics workspace Application Insights uses, so
      // a pod's logs and a case's traces are queryable side by side.
      omsagent: {
        enabled: true
        config: {
          logAnalyticsWorkspaceResourceID: logAnalyticsWorkspaceId
        }
      }
      // The Key Vault CSI driver: mounts secrets into a pod as files. See the SecretProviderClass
      // in the Helm chart.
      azureKeyvaultSecretsProvider: {
        enabled: true
        config: {
          enableSecretRotation: 'true'
          rotationPollInterval: '5m'
        }
      }
    }

    autoUpgradeProfile: {
      // Patch-level upgrades only, and only in a maintenance window. `none` would leave known
      // CVEs unpatched; `stable` could move the minor version under a running demo.
      upgradeChannel: 'patch'
    }

    disableLocalAccounts: false
  }
}

output id string = cluster.id
output name string = cluster.name
output oidcIssuerUrl string = cluster.properties.oidcIssuerProfile.issuerURL
@description('The identity AKS pulls images with. It is this that needs AcrPull, not the workload identity.')
output kubeletPrincipalId string = cluster.properties.identityProfile.kubeletidentity.objectId
output nodeResourceGroup string = cluster.properties.nodeResourceGroup

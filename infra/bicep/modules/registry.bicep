// Azure Container Registry — where the images AKS pulls are pushed.
//
// Basic tier, about USD 5/month for 10 GB. The difference from Standard is included storage
// and throughput, neither of which a four-image demo comes near.
//
// `adminUserEnabled: false` is the point worth noticing. The admin user is a single shared
// username and password with push rights over the whole registry — convenient, and exactly the
// credential that ends up pasted into a CI variable and never rotated. AKS pulls with its
// kubelet identity instead (the `AcrPull` assignment in `identity.bicep`), and a developer
// pushes with `az acr login`, which uses their own Entra token.

param location string
param name string
param tags object

resource registry 'Microsoft.ContainerRegistry/registries@2023-11-01-preview' = {
  name: name
  location: location
  tags: tags
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: false
    publicNetworkAccess: 'Enabled'
    anonymousPullEnabled: false
  }
}

output id string = registry.id
output name string = registry.name
output loginServer string = registry.properties.loginServer

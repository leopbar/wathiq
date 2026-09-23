// Azure OpenAI (the model provider behind Azure AI Foundry).
//
// ─────────────────────────────────────────────────────────────────────────────
// QUOTA IS SHARED, AND THAT IS THE RISK THIS FILE MANAGES.
//
// Azure OpenAI capacity is granted per SUBSCRIPTION, per REGION, per MODEL, per SKU — not per
// account. So creating a second account is free of consequence, but giving it a deployment
// that draws on a pool something else is already using can throttle that other system.
//
// This subscription's existing workload uses:
//   * gpt-4o                 Standard        (10 of 50 TPM units)
//   * text-embedding-3-small GlobalStandard  (150 of 3000)
//
// Wathiq therefore uses DIFFERENT pools:
//   * gpt-4.1-mini           Standard        (0 of 200)
//   * text-embedding-3-small Standard        (0 of 350)   ← Standard, not GlobalStandard
//
// Changing `chatModelName` to gpt-4o, or either deployment's SKU to GlobalStandard, would move
// Wathiq onto a pool the other system depends on. Check the headroom first:
//   az cognitiveservices usage list -l <region> -o table
//
// A second, unrelated trap: a model version can be refused by the deployment preflight while
// `az cognitiveservices model list` still advertises it as available. gpt-4o-mini 2024-07-18
// was the first choice here and failed exactly that way, after the resource group had already
// been created. The list is not the authority; the preflight is.
// ─────────────────────────────────────────────────────────────────────────────

param location string
param name string
param tags object

param chatModelName string
param chatModelVersion string
param chatModelCapacity int

param embeddingModelName string
param embeddingModelVersion string
param embeddingModelCapacity int

resource account 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: name
  location: location
  tags: tags
  kind: 'OpenAI'
  sku: {
    // S0 is the only SKU Azure OpenAI offers. It is pay-per-token, so an idle deployment
    // costs nothing — which is why the demo can leave it deployed without a standing bill.
    name: 'S0'
  }
  properties: {
    // The subdomain is required for token-based auth: Entra will not issue a token for the
    // regional endpoint, only for `https://<name>.openai.azure.com`.
    customSubDomainName: name
    publicNetworkAccess: 'Enabled'
    networkAcls: {
      defaultAction: 'Allow'
    }
    // Turns off authentication by API key entirely. Wathiq authenticates with its workload
    // identity, so a key is not needed — and a key that does not exist cannot leak.
    disableLocalAuth: true
  }
}

resource chatDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: account
  name: chatModelName
  sku: {
    name: 'Standard'
    capacity: chatModelCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: chatModelName
      version: chatModelVersion
    }
    // Fail the request rather than silently truncating context.
    versionUpgradeOption: 'OnceCurrentVersionExpired'
    raiPolicyName: 'Microsoft.DefaultV2'
  }
}

resource embeddingDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: account
  name: embeddingModelName
  sku: {
    name: 'Standard'
    capacity: embeddingModelCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: embeddingModelName
      version: embeddingModelVersion
    }
    versionUpgradeOption: 'OnceCurrentVersionExpired'
  }
  dependsOn: [
    // Deployments on one account must be created one at a time; in parallel the second gets a
    // conflict on the account's own state.
    chatDeployment
  ]
}

output id string = account.id
output name string = account.name
output endpoint string = account.properties.endpoint
output chatDeploymentName string = chatDeployment.name
output embeddingDeploymentName string = embeddingDeployment.name

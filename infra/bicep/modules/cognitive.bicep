// One Cognitive Services account, of whichever kind is asked for.
//
// Used twice: Document Intelligence (`FormRecognizer`) and Content Safety (`ContentSafety`).
// They are the same resource type with a different `kind`, so one parameterised module is
// honest about that rather than two near-identical files drifting apart.
//
// **Free tiers are one per subscription per kind**, and this subscription's Content Safety F0
// is already taken by another system — so Content Safety is deployed as S0 and
// Document Intelligence as F0. `main.bicep` passes the SKU, with the reasoning at the call site.

param location string
param name string
param tags object

@description('FormRecognizer (Document Intelligence), ContentSafety, TextAnalytics, ...')
param kind string

@description('F0 is free and limited; S0 is pay-per-call.')
@allowed(['F0', 'S0'])
param skuName string

resource account 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: name
  location: location
  tags: tags
  kind: kind
  sku: {
    name: skuName
  }
  properties: {
    // Required for Entra token auth, exactly as for the OpenAI account.
    customSubDomainName: name
    publicNetworkAccess: 'Enabled'
    networkAcls: {
      defaultAction: 'Allow'
    }
    // Key auth off: the pods use their workload identity.
    disableLocalAuth: true
  }
}

output id string = account.id
output name string = account.name
output endpoint string = account.properties.endpoint

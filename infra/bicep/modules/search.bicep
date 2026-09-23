// Azure AI Search — only when `deployAiSearch` is true, which it is not by default.
//
// The free tier is one search service per subscription and this subscription's is already in
// use by another system. Taking it is not possible, and paying about USD 74/month for a Basic
// service to do what the pgvector retriever already does correctly is not worth it for a demo.
// So `app/azure/search.py` is written and tested, and this module sits ready behind a flag.
//
// `authOptions` is absent on purpose: omitting it leaves the service on Entra-only auth, so
// there are no API keys to leak. The workload identity gets `Search Index Data Reader`.

param location string
param name string
param tags object

@description('Basic is the smallest paid tier. Free cannot be used here — see the note above.')
@allowed(['basic', 'standard'])
param skuName string = 'basic'

resource search 'Microsoft.Search/searchServices@2024-06-01-preview' = {
  name: name
  location: location
  tags: tags
  sku: {
    name: skuName
  }
  properties: {
    replicaCount: 1
    partitionCount: 1
    hostingMode: 'default'
    publicNetworkAccess: 'enabled'
    // Entra only. With this set, an API key is not accepted even if one exists.
    disableLocalAuth: true
    semanticSearch: 'disabled'
  }
}

output id string = search.id
output name string = search.name
output endpoint string = 'https://${search.name}.search.windows.net'

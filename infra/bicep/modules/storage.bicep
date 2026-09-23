// ADLS Gen2: uploaded documents and golden-set archives.
//
// `isHnsEnabled: true` is what makes this ADLS Gen2 rather than plain blob storage. With a
// hierarchical namespace, `case-id/licence.pdf` is a real directory holding a real file, which
// buys a per-directory ACL (access granted per case, not per container) and an atomic rename.
// It cannot be switched on after the account is created, so it has to be right here.
//
// `documents` is the filesystem `app/azure/adls.py` writes to, matching
// `WATHIQ_AZURE_STORAGE_FILESYSTEM`.
//
// **Azure ML cannot use an HNS account**, which is why this module is parameterised and
// instantiated twice. A workspace refuses a storage account with a hierarchical namespace
// outright ("Cannot use storage with HNS enabled"), so Wathiq's documents live in the HNS
// account and the ML workspace gets a plain one of its own. Two small accounts cost the same
// as one; giving up the hierarchical namespace to share a single account would give up the
// per-case ACL that was the reason to choose ADLS Gen2.

param location string
param name string
param tags object

@description('The filesystem uploaded documents go into.')
param filesystemName string = 'documents'

@description('Hierarchical namespace. True for the documents account (that is what makes it ADLS Gen2); false for the Azure ML account, which refuses an HNS account.')
param enableHierarchicalNamespace bool = true

@description('Create the documents container. The ML workspace makes its own.')
param createDocumentsContainer bool = true

resource account 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: name
  location: location
  tags: tags
  sku: {
    // Locally redundant. A demo does not need three copies in three zones, and ZRS costs more.
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    isHnsEnabled: enableHierarchicalNamespace
    accessTier: 'Hot'
    // TLS 1.2 or nothing, and no unencrypted traffic at all.
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
    allowBlobPublicAccess: false
    // Shared-key access is left ON only because an Azure ML workspace still requires it.
    // Wathiq itself never uses it: `app/azure/adls.py` prefers the managed identity, and the
    // SAS links it hands the browser are signed with a user delegation key, which is issued
    // by Entra and traceable to the identity that asked for it.
    allowSharedKeyAccess: true
    publicNetworkAccess: 'Enabled'
    networkAcls: {
      defaultAction: 'Allow'
      bypass: 'AzureServices'
    }
    encryption: {
      services: {
        blob: {
          enabled: true
        }
        file: {
          enabled: true
        }
      }
      keySource: 'Microsoft.Storage'
    }
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: account
  name: 'default'
  properties: {
    // Seven days of soft delete: a document deleted by mistake during a demo is recoverable,
    // and the storage cost of keeping deleted blobs for a week is negligible at this volume.
    deleteRetentionPolicy: {
      enabled: true
      days: 7
    }
  }
}

resource documents 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = if (createDocumentsContainer) {
  parent: blobService
  name: filesystemName
  properties: {
    publicAccess: 'None'
  }
}

output id string = account.id
output name string = account.name
output filesystemName string = filesystemName
@description('The dfs endpoint, which is what WATHIQ_AZURE_STORAGE_ACCOUNT_URL expects — the blob endpoint would not give the Data Lake API.')
output dfsEndpoint string = account.properties.primaryEndpoints.dfs

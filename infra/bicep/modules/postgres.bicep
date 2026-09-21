// PostgreSQL Flexible Server — the same database the compose stack runs, managed.
//
// **pgvector is not optional here.** Wathiq stores policy embeddings in a `vector(256)` column
// and the LangGraph checkpointer lives in this database too. `azure.extensions` is an
// allow-list: an extension that is not named in it cannot be created even by a superuser, so
// `CREATE EXTENSION vector` in the Alembic migration would fail with a permission error that
// looks nothing like its cause. Naming it here is what makes the existing migration work
// unchanged.
//
// Cost: B1ms burstable, 32 GB. About USD 16/month, the smallest thing that runs this.

param location string
param name string
param tags object
param adminUser string

@secure()
param adminPassword string

@description('The application database. Created here so the app never needs server-level rights.')
param databaseName string = 'wathiq'

resource server 'Microsoft.DBforPostgreSQL/flexibleServers@2024-08-01' = {
  name: name
  location: location
  tags: tags
  sku: {
    name: 'Standard_B1ms'
    tier: 'Burstable'
  }
  properties: {
    version: '16'
    administratorLogin: adminUser
    administratorLoginPassword: adminPassword
    storage: {
      storageSizeGB: 32
      autoGrow: 'Disabled'
    }
    backup: {
      // The minimum. A demo database is rebuilt by re-running the seed, so paying to keep
      // more than a week of backups would buy nothing.
      backupRetentionDays: 7
      geoRedundantBackup: 'Disabled'
    }
    highAvailability: {
      // A standby replica doubles the bill. Production would want ZoneRedundant.
      mode: 'Disabled'
    }
    network: {
      publicNetworkAccess: 'Enabled'
    }
  }
}

resource database 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2024-08-01' = {
  parent: server
  name: databaseName
  properties: {
    charset: 'UTF8'
    collation: 'en_US.utf8'
  }
}

// The extension allow-list. `vector` is required; `uuid-ossp` and `pg_trgm` are there because
// the schema uses UUID keys and trigram matching is the obvious next step for name search.
resource extensions 'Microsoft.DBforPostgreSQL/flexibleServers/configurations@2024-08-01' = {
  parent: server
  name: 'azure.extensions'
  properties: {
    value: 'VECTOR,UUID-OSSP,PG_TRGM'
    source: 'user-override'
  }
}

// Lets other Azure services — the AKS nodes' egress address among them — reach the server.
//
// This is the demo posture and it is stated plainly rather than hidden: the server is
// reachable from Azure, protected by a password and TLS. A bank deployment would replace this
// with a private endpoint and a VNet-integrated cluster, which is a network design rather than
// a line of Bicep. See DECISIONS #76.
resource allowAzureServices 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2024-08-01' = {
  parent: server
  name: 'AllowAllAzureServicesAndResources'
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '0.0.0.0'
  }
  dependsOn: [
    database
  ]
}

output id string = server.id
output name string = server.name
output fqdn string = server.properties.fullyQualifiedDomainName
output databaseName string = database.name

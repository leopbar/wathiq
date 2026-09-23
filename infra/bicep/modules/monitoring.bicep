// Log Analytics + Application Insights.
//
// Application Insights is "workspace-based": it needs a Log Analytics workspace to store the
// data in. The classic, standalone kind is retired, so this is not a choice.
//
// Cost: both are pay-per-GB with a 5 GB/month free grant, which a demo never comes close to
// using. The 30-day retention below is the free default; leaving it explicit means nobody has
// to wonder whether a longer, billed retention was switched on by accident.

param location string
param baseName string
param tags object

resource workspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: '${baseName}-logs'
  location: location
  tags: tags
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
    features: {
      // Stops anything but the workspace's own access rules granting data access.
      enableLogAccessUsingOnlyResourcePermissions: true
    }
  }
}

resource applicationInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: '${baseName}-insights'
  location: location
  tags: tags
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: workspace.id
    // Wathiq sends spans itself through the OpenTelemetry exporter in `app/azure/monitor.py`.
    // Nothing is ingested from a browser, so public network access for ingestion is all that
    // is needed and query access stays on the workspace's rules.
    IngestionMode: 'LogAnalytics'
    publicNetworkAccessForIngestion: 'Enabled'
    publicNetworkAccessForQuery: 'Enabled'
  }
}

output logAnalyticsWorkspaceId string = workspace.id
output applicationInsightsId string = applicationInsights.id
output applicationInsightsName string = applicationInsights.name
@description('Carries an instrumentation key, so it is a secret in practice — the deploy script writes it to Key Vault, never to a file in the repository.')
output connectionString string = applicationInsights.properties.ConnectionString

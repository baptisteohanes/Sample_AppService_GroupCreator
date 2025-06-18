@description('Base name of the resource such as web app name and app service plan')
param baseName string = 'groupcreator${uniqueString(resourceGroup().id)}'

@description('Location for all resources.')
param location string = resourceGroup().location

@description('Environment name')
@allowed([
  'dev'
  'test'
  'prod'
])
param environmentName string = 'dev'

@description('App Service Plan SKU')
param appServicePlanSku string = 'B1'

@description('Azure Tenant ID where security groups will be created')
@secure()
param tenantId string

@description('Client ID (Application ID) of the Service Principal')
@secure()
param clientId string

@description('Client Secret of the Service Principal')
@secure()
param clientSecret string

var appServicePlanName = 'plan-${baseName}'
var webAppName = 'app-${baseName}'

// Tags for all resources
var tags = {
  environment: environmentName
  application: 'GroupCreator'
}

// App Service Plan
resource appServicePlan 'Microsoft.Web/serverfarms@2022-03-01' = {
  name: appServicePlanName
  location: location
  tags: tags
  sku: {
    name: appServicePlanSku
  }
  kind: 'linux'
  properties: {
    reserved: true // Required for Linux app service plans
  }
}

// Web App
resource webApp 'Microsoft.Web/sites@2022-03-01' = {
  name: webAppName
  location: location
  tags: tags
  kind: 'app,linux'
  properties: {
    serverFarmId: appServicePlan.id
    httpsOnly: true
    siteConfig: {
      linuxFxVersion: 'PYTHON|3.11'
      minTlsVersion: '1.2'
      ftpsState: 'Disabled'
    }
  }
}

// Application Insights for monitoring
resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: 'insights-${baseName}'
  location: location
  tags: tags
  kind: 'web'
  properties: {
    Application_Type: 'web'
    Flow_Type: 'Bluefield'
    Request_Source: 'rest'
  }
}

// Dedicated App Settings resource - This ensures app settings are properly applied
resource webAppSettings 'Microsoft.Web/sites/config@2022-03-01' = {
  parent: webApp
  name: 'appsettings'
  properties: {
    SCM_DO_BUILD_DURING_DEPLOYMENT: 'true'
    ENABLE_ORYX_BUILD: 'true'
    AZURE_TENANT_ID: tenantId
    AZURE_CLIENT_ID: clientId
    AZURE_CLIENT_SECRET: clientSecret
    SECRET_KEY: guid(resourceGroup().id, webAppName)
    WEBSITE_HTTPLOGGING_RETENTION_DAYS: '7'
    APPINSIGHTS_INSTRUMENTATIONKEY: appInsights.properties.InstrumentationKey
    ApplicationInsightsAgent_EXTENSION_VERSION: '~3'
  }
}

// Add Application Insights settings to web app
resource appInsightsSettings 'Microsoft.Web/sites/config@2022-03-01' = {
  parent: webApp
  name: 'metadata'
  properties: {
    APPINSIGHTS_INSTRUMENTATIONKEY: appInsights.properties.InstrumentationKey
  }
  dependsOn: [
    webAppSettings
  ]
}

// Output the web app URL and useful information
output webAppUrl string = 'https://${webApp.properties.defaultHostName}'
output webAppName string = webApp.name
output appInsightsName string = appInsights.name
output appInsightsInstrumentationKey string = appInsights.properties.InstrumentationKey
output deploymentComplete bool = true

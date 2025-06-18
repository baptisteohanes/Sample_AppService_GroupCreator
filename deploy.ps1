# Deploy the Group Creator application to Azure App Service

# Set variables for resource group
$resourceGroupName = "rg-web-groupcreator"
$location = "West Europe" # Change to your preferred region

# Set variables for Bicep deployment
$deploymentName = "groupcreator-deployment-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
$bicepFilePath = ".\infra\main.bicep"
$parametersFilePath = ".\infra\main.parameters.json"

# Prompt for Service Principal details if not already in parameters file
Write-Host "Checking parameters file for Service Principal details..."
$paramsContent = Get-Content -Path $parametersFilePath -Raw | ConvertFrom-Json
$tenantId = $paramsContent.parameters.tenantId.value
$clientId = $paramsContent.parameters.clientId.value
$clientSecret = $paramsContent.parameters.clientSecret.value

if ([string]::IsNullOrEmpty($tenantId) -or [string]::IsNullOrEmpty($clientId) -or [string]::IsNullOrEmpty($clientSecret)) {
    Write-Host "Service Principal details not found in parameters file. Please enter them now."
    
    if ([string]::IsNullOrEmpty($tenantId)) {
        $tenantId = Read-Host -Prompt "Enter your Tenant ID"
    }
    
    if ([string]::IsNullOrEmpty($clientId)) {
        $clientId = Read-Host -Prompt "Enter your Client ID (Application ID)"
    }
    
    if ([string]::IsNullOrEmpty($clientSecret)) {
        $clientSecret = Read-Host -Prompt "Enter your Client Secret" -AsSecureString
        $BSTR = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($clientSecret)
        $clientSecret = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($BSTR)
    }
}

# Login to Azure if not already logged in
Write-Host "Checking Azure login status..."
$context = Get-AzContext
if (!$context) {
    Write-Host "Please login to Azure..."
    Connect-AzAccount
}

# Create Resource Group if it doesn't exist
Write-Host "Creating resource group if it doesn't exist..."
$rg = Get-AzResourceGroup -Name $resourceGroupName -ErrorAction SilentlyContinue
if (!$rg) {
    Write-Host "Creating resource group '$resourceGroupName' in location '$location'..."
    New-AzResourceGroup -Name $resourceGroupName -Location $location
}
# Convert parameters to secure strings
$secTenantId = ConvertTo-SecureString $tenantId -AsPlainText -Force
$secClientId = ConvertTo-SecureString $clientId -AsPlainText -Force
$secClientSecret = ConvertTo-SecureString $clientSecret -AsPlainText -Force

# Validate the Bicep deployment
Write-Host "Validating deployment..."
$validation = Test-AzResourceGroupDeployment -ResourceGroupName $resourceGroupName `
    -TemplateFile $bicepFilePath `
    -TemplateParameterFile $parametersFilePath `
    -tenantId $secTenantId `
    -clientId $secClientId `
    -clientSecret $secClientSecret

if ($validation) {
    Write-Host "Validation errors found:"
    $validation | Format-List
    exit 1
}



# Preview the changes with What-If
Write-Host "Previewing changes with What-If..."
Get-AzResourceGroupDeploymentWhatIfResult -ResourceGroupName $resourceGroupName `
    -TemplateFile $bicepFilePath `
    -TemplateParameterFile $parametersFilePath `
    -tenantId $secTenantId `
    -clientId $secClientId `
    -clientSecret $secClientSecret

# Confirm before proceeding
$confirmation = Read-Host "Do you want to proceed with the deployment? (y/n)"
if ($confirmation -ne 'y') {
    Write-Host "Deployment cancelled."
    exit
}

# Deploy the infrastructure
Write-Host "Deploying infrastructure..."
$deployment = New-AzResourceGroupDeployment -Name $deploymentName `
    -ResourceGroupName $resourceGroupName `
    -TemplateFile $bicepFilePath `
    -TemplateParameterFile $parametersFilePath `
    -tenantId $secTenantId `
    -clientId $secClientId `
    -clientSecret $secClientSecret

if ($deployment.ProvisioningState -eq "Succeeded") {
    Write-Host "Infrastructure deployment successful!"
    $webAppName = $deployment.Outputs.webAppName.Value
    $webAppUrl = $deployment.Outputs.webAppUrl.Value
    
    # Create a zip deployment package
    Write-Host "Creating deployment package..."
    $deploymentPackagePath = ".\deployment.zip"
    $filesToInclude = @("app.py", "requirements.txt", "startup.txt", "templates")
    
    # Remove existing zip file if it exists
    if (Test-Path $deploymentPackagePath) {
        Remove-Item $deploymentPackagePath -Force
    }
    
    # Create the zip file
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $compressionLevel = [System.IO.Compression.CompressionLevel]::Optimal
    
    # Create a temporary directory to ensure proper structure
    $tempDir = ".\temp"
    if (Test-Path $tempDir) {
        Remove-Item $tempDir -Recurse -Force
    }
    New-Item -ItemType Directory -Path $tempDir
    
    # Copy files to temp directory
    foreach ($item in $filesToInclude) {
        if (Test-Path $item) {
            if ((Get-Item $item) -is [System.IO.DirectoryInfo]) {
                Copy-Item -Path $item -Destination $tempDir -Recurse
            } else {
                Copy-Item -Path $item -Destination $tempDir
            }
        } else {
            Write-Warning "Item not found: $item"
        }
    }
    
    # Create the zip file from the temp directory
    [System.IO.Compression.ZipFile]::CreateFromDirectory($tempDir, $deploymentPackagePath, $compressionLevel, $false)
    
    # Clean up temp directory
    Remove-Item $tempDir -Recurse -Force
    
    # Deploy the application code
    Write-Host "Deploying application code to Azure App Service..."
    $publishResult = Publish-AzWebApp -ResourceGroupName $resourceGroupName -Name $webAppName -ArchivePath $deploymentPackagePath -Force
    
    Write-Host "Deployment completed successfully!"
    Write-Host "Web App Name: $webAppName"
    Write-Host "Web App URL: $webAppUrl"
} else {
    Write-Host "Deployment failed with state: $($deployment.ProvisioningState)"
    exit 1
}

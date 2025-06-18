# Security Group Creator - Azure App Service

This Flask application allows you to create security groups in Entra ID through a web interface. It is designed to be deployed to Azure App Service.

## Features

- Simple web interface for Entra ID security group creation
- Input validation and error handling
- Flash messages for success/error feedback
- Health check endpoint for monitoring
- Azure App Service deployment ready

## Prerequisites

1. **Azure Account** with permissions to create App Service resources
2. **Entra ID Service Principal** with permissions to create security groups
3. **Required Permissions for Service Principal**:
   - `Group.Create` (Application permission)
   - `Group.ReadWrite.All` (Application permission)
   - `Directory.ReadWrite.All` (Application permission)

## Setup Service Principal

1. Register an application in Entra ID:

   ```powershell
   az ad app create --display-name "GroupCreatorApp"
   ```

2. Create a service principal:

   ```powershell
   az ad sp create --id <app-id>
   ```

3. Create a client secret:

   ```powershell
   az ad app credential reset --id <app-id> --credential-description "Group Creator"
   ```

4. Grant required permissions:

   ```powershell
   az ad app permission add --id <app-id> --api 00000003-0000-0000-c000-000000000000 --api-permissions bf7b1a76-6e77-406b-b258-bf5c7720e98f=Role 62a82d76-70ea-41e2-9197-370581804d09=Role 19dbc75e-c2e2-444c-a770-ec69d8559fc7=Role
   az ad app permission admin-consent --id <app-id>
   ```

## Local Development

1. Clone this repository:

   ```bash
   git clone https://github.com/yourusername/groupcreator.git
   cd groupcreator
   ```

2. Create a virtual environment:

   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate
   ```

3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

4. Create a `.env` file from the example:

   ```powershell
   Copy-Item .env.example .env
   ```

5. Update the `.env` file with your Service Principal credentials:

   ```text
   AZURE_TENANT_ID=your-tenant-id
   AZURE_CLIENT_ID=your-client-id
   AZURE_CLIENT_SECRET=your-client-secret
   SECRET_KEY=your-secret-key
   ```

6. Run the application:

   ```bash
   python app.py
   ```

7. Access the application at [http://localhost:8000](http://localhost:8000)

## Azure Deployment

### Option 1: PowerShell Deployment Script

1. Update the `infra/main.parameters.json` file with your preferred settings.

2. Run the deployment script:

   ```powershell
   .\deploy.ps1
   ```

3. Follow the prompts to complete the deployment.

### Option 2: Azure Portal Deployment

1. Create an App Service in Azure Portal
2. Set up Deployment Center to connect to your repository
3. Configure the following Application Settings:
   - AZURE_TENANT_ID
   - AZURE_CLIENT_ID
   - AZURE_CLIENT_SECRET
   - SECRET_KEY

## Project Structure

```text
Sample_AppService_GroupCreator/
├── app.py                 # Main Flask application
├── requirements.txt       # Python dependencies
├── startup.txt            # Azure App Service startup command
├── .env.example           # Environment variables example
├── deploy.ps1             # Deployment script
├── templates/
│   └── index.html         # HTML template for the web interface
└── infra/
    ├── main.bicep         # Infrastructure as Code (Bicep)
    └── main.parameters.json # Parameters for Bicep deployment
```

## Security Considerations

- Never commit credentials to source control
- Use Azure Key Vault for production secrets
- Consider implementing authentication for the web interface
- Monitor and audit group creation activities

## Troubleshooting

- Check App Service logs for application errors
- Use the `/health` endpoint to verify the application is running correctly
- Verify that the Service Principal has the required permissions
- Check that the environment variables are correctly set in App Service

## License

This project is licensed under the MIT License. See the LICENSE file for details.

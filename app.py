from flask import Flask, render_template, request, flash, redirect, url_for
import os
import logging
from azure.identity import ClientSecretCredential
import requests
import json
import asyncio
from dotenv import load_dotenv
load_dotenv()


app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-change-this')

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Azure AD configuration
TENANT_ID = os.environ.get('AZURE_TENANT_ID')
CLIENT_ID = os.environ.get('AZURE_CLIENT_ID')
CLIENT_SECRET = os.environ.get('AZURE_CLIENT_SECRET')

def get_access_token():
    """Get Microsoft Graph API access token using client credentials flow"""
    try:
        credential = ClientSecretCredential(
            tenant_id=TENANT_ID,
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET
        )
        
        # Get token for Microsoft Graph API
        access_token = credential.get_token("https://graph.microsoft.com/.default")
        return access_token.token
    except Exception as e:
        logger.error(f"Error getting access token: {str(e)}")
        return None
        
def get_graph_client():
    """Initialize and return a custom client for Microsoft Graph API calls"""
    try:
        token = get_access_token()
        if not token:
            return None
        
        # Create a wrapper class instead of modifying the session directly
        class GraphClient:
            def __init__(self, token):
                self.session = requests.Session()
                self.session.headers.update({
                    'Authorization': f'Bearer {token}',
                    'Content-Type': 'application/json'
                })
                self.base_url = "https://graph.microsoft.com/v1.0"
                
            def post(self, endpoint, data):
                url = f"{self.base_url}{endpoint}"
                return self.session.post(url, data=data)
        
        # Return the client instance
        return GraphClient(token)
    except Exception as e:
        logger.error(f"Error creating Graph client: {str(e)}")
        return None

def create_security_group(group_name):
    """Create a security group in Entra ID"""
    try:
        graph_client = get_graph_client()
        if not graph_client:
            return False, "Failed to initialize Graph client"
        
        # Create the group object
        group_data = {
            "displayName": group_name,
            "mailNickname": group_name.replace(' ', '').lower(),
            "securityEnabled": True,
            "mailEnabled": False,
            "groupTypes": []
        }
        
        # Make the request to create the group
        endpoint = "/groups"
        response = graph_client.post(endpoint, json.dumps(group_data))
        
        if response.status_code == 201:
            result = response.json()
            logger.info(f"Successfully created group: {group_name}, ID: {result.get('id', 'Unknown')}")
            return True, f"Security group '{group_name}' created successfully"
        else:
            logger.error(f"Failed to create group. Status code: {response.status_code}, Response: {response.text}")
            return False, f"Failed to create group: {response.text}"
            
    except Exception as e:
        logger.error(f"Error creating group: {str(e)}")
        return False, f"Error creating group: {str(e)}"

@app.route('/')
def index():
    """Main page with the form"""
    return render_template('index.html')

@app.route('/create_group', methods=['POST'])
def create_group_route():
    """Handle group creation request"""
    group_name = request.form.get('group_name', '').strip()
    
    if not group_name:
        flash('Please enter a group name', 'error')
        return redirect(url_for('index'))
    
    # Validate group name
    if len(group_name) < 1 or len(group_name) > 64:
        flash('Group name must be between 1 and 64 characters', 'error')
        return redirect(url_for('index'))
    
    # Create the group
    success, message = create_security_group(group_name)
    
    if success:
        flash(message, 'success')
    else:
        flash(message, 'error')
    
    return redirect(url_for('index'))

@app.route('/health')
def health_check():
    """Health check endpoint for Azure App Service"""
    # Check if we can initialize the Graph client
    client = get_graph_client()
    if client is None:
        return {'status': 'unhealthy', 'details': 'Could not initialize Graph client'}, 500
    
    return {'status': 'healthy'}, 200

if __name__ == '__main__':
    # Check if required environment variables are set
    required_vars = ['AZURE_TENANT_ID', 'AZURE_CLIENT_ID', 'AZURE_CLIENT_SECRET']
    missing_vars = [var for var in required_vars if not os.environ.get(var)]
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        print(f"Please set the following environment variables: {', '.join(missing_vars)}")
    else:
        app.run(debug=False, host='0.0.0.0', port=int(os.environ.get('PORT', 8000)))

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
                
            def patch(self, endpoint, data):
                url = f"{self.base_url}{endpoint}"
                return self.session.patch(url, data=data)
        
        # Return the client instance
        return GraphClient(token)
    except Exception as e:
        logger.error(f"Error creating Graph client: {str(e)}")
        return None

def create_security_group(group_name, owner_id=None):
    """Create a security group in Entra ID and optionally add an owner"""
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
        
        # Add owner during creation if provided
        if owner_id:
            group_data["owners@odata.bind"] = [f"https://graph.microsoft.com/v1.0/directoryObjects/{owner_id}"]
        
        # Make the request to create the group
        endpoint = "/groups"
        response = graph_client.post(endpoint, json.dumps(group_data))
        
        if response.status_code == 201:
            result = response.json()
            group_id = result.get('id', 'Unknown')
            logger.info(f"Successfully created group: {group_name}, ID: {group_id}")
            
            # If owner_id was provided but not set during creation, add as owner separately
            if owner_id and "owners@odata.bind" not in group_data:
                add_owner_success = add_group_owner(group_id, owner_id)
                if not add_owner_success:
                    logger.warning(f"Group created but failed to add owner {owner_id}")
            
            owner_msg = f" with owner {owner_id}" if owner_id else ""
            return True, f"Security group '{group_name}' created successfully{owner_msg}"
        else:
            logger.error(f"Failed to create group. Status code: {response.status_code}, Response: {response.text}")
            return False, f"Failed to create group: {response.text}"
            
    except Exception as e:
        logger.error(f"Error creating group: {str(e)}")
        return False, f"Error creating group: {str(e)}"

def add_group_owner(group_id, owner_id):
    """Add an owner to an existing group"""
    try:
        graph_client = get_graph_client()
        if not graph_client:
            logger.error("Failed to initialize Graph client for adding owner")
            return False
        
        # Prepare the owner data
        owner_data = {
            "@odata.id": f"https://graph.microsoft.com/v1.0/directoryObjects/{owner_id}"
        }
        
        # Add owner to the group
        endpoint = f"/groups/{group_id}/owners/$ref"
        response = graph_client.post(endpoint, json.dumps(owner_data))
        
        if response.status_code == 204:
            logger.info(f"Successfully added owner {owner_id} to group {group_id}")
            return True
        else:
            logger.error(f"Failed to add owner. Status code: {response.status_code}, Response: {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"Error adding group owner: {str(e)}")
        return False

def get_current_user_id():
    """Get current user's object ID from EasyAuth headers"""
    try:
        # EasyAuth provides user information in headers
        user_id = request.headers.get('X-MS-CLIENT-PRINCIPAL-ID')
        if user_id:
            logger.info(f"Retrieved user ID from EasyAuth: {user_id}")
            return user_id
        
        # Fallback: Parse the X-MS-CLIENT-PRINCIPAL header if available
        principal_header = request.headers.get('X-MS-CLIENT-PRINCIPAL')
        if principal_header:
            import base64
            decoded = base64.b64decode(principal_header).decode('utf-8')
            principal_data = json.loads(decoded)
            user_id = principal_data.get('oid') or principal_data.get('sub')
            if user_id:
                logger.info(f"Retrieved user ID from principal header: {user_id}")
                return user_id
        
        logger.warning("No user ID found in EasyAuth headers")
        return None
    except Exception as e:
        logger.error(f"Error extracting user ID from EasyAuth: {str(e)}")
        return None

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
    
    # Get current authenticated user ID from EasyAuth
    current_user_id = get_current_user_id()
    if not current_user_id:
        logger.warning("Could not retrieve current user ID from EasyAuth headers")
        flash('Warning: Could not determine current user. Group will be created without owner.', 'warning')
    
    # Create the group with current user as owner
    success, message = create_security_group(group_name, current_user_id)
    
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

import base64
import json
import os
import logging
import boto3
from dotenv import load_dotenv
from fastapi import HTTPException

load_dotenv()

# AWS
AWS_REGION="us-east-1"

# Firebase
FIREBASE_SECRET="firebase_sdk"
FIREBASE_DATABASE_URL=''

# Frontend
FRONTEND_URL="http://localhost:5173"

# Github
GITHUB_CLIENT_ID = os.getenv("CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("CLIENT_SECRET")
GITHUB_REDIRECT_URI = os.getenv("REDIRECT_URI")
GITHUB_ACCESS_TOKEN_URL="https://github.com/login/oauth/access_token"
GITHUB_USER_URL="https://api.github.com/user"

OPENAI = os.getenv("OPENAI")
PINECONE = os.getenv("PINECONE")

# Get Firebase SDK from AWS Secrets
def get_sdk_secret():
    """
    Retrieve the Firebase SDK secret from AWS Secrets Manager.

    Returns:
        dict: The Firebase SDK secret as a dictionary.

    Raises:
        HTTPException: If there's an error retrieving the secret.
    """
    secret_name = FIREBASE_SECRET
    region_name = AWS_REGION
    session = boto3.session.Session()
    client = session.client(
        service_name='secretsmanager',
        region_name=region_name
    )
    try:
        get_secret_value_response = client.get_secret_value(SecretId=secret_name)
    except Exception as e:
        logging.error(f"Error retrieving secret in get sdk: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving secret: {str(e)}")
    else:
        if 'SecretString' in get_secret_value_response:
            return json.loads(get_secret_value_response['SecretString'])

# Get Github Secret from AWS Secrets
def get_secret(secret_name, key_name):
    """
    Retrieve a specific secret from AWS Secrets Manager.

    Args:
        secret_name (str): The name of the secret in AWS Secrets Manager.
        key_name (str): The key of the specific secret to retrieve.

    Returns:
        str: The value of the specified secret.

    Raises:
        HTTPException: If there's an error connecting to AWS or retrieving the secret.
    """
    try:
        region_name = AWS_REGION
        session = boto3.session.Session()
        client = session.client(
            service_name='secretsmanager',
            region_name=region_name
        )
        credentials = session.get_credentials()
        if credentials is None:
            raise ValueError("AWS credentials not found.")
    except Exception as e:
        logging.error(f"Error connecting to AWS in get secret: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Could not connect to AWS Secrets Manager: {str(e)}")
    
    try:
        get_secret_value_response = client.get_secret_value(SecretId=secret_name)
        if 'SecretString' in get_secret_value_response:
            secret = get_secret_value_response['SecretString']
        else:
            secret = base64.b64decode(get_secret_value_response['SecretBinary'])
        
        secret = secret.replace('\n', '\\n')
        secret_dict = json.loads(secret)
        secret_dict[key_name] = secret_dict[key_name].replace('\\n', '\n')
        
        return secret_dict[key_name]

    except Exception as e:
        logging.error(f"Error retrieving secret in get secret: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Could not retrieve secret: {str(e)}")
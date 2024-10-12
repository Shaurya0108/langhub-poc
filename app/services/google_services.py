from typing import Any, Dict
from fastapi import HTTPException, Request
from firebase_admin import auth
import logging

async def get_current_user(request: Request) -> dict:
    """
    Authenticate the current user based on the Authorization header.

    This function extracts the JWT token from the Authorization header,
    verifies it using Firebase Authentication, and returns the decoded
    token information.

    Args:
        request (Request): The FastAPI request object.

    Returns:
        dict: The decoded token containing user information.

    Raises:
        HTTPException: If the token is missing or invalid.
    """
    token = request.headers.get("Authorization")
    if not token:
        logging.warning("Missing authentication token")
        raise HTTPException(status_code=401, detail="Missing authentication token")
    
    try:
        # Extract the token from the "Bearer" prefix
        token_value = token.split("Bearer ")[1]
        decoded_token = auth.verify_id_token(token_value)
        logging.info(f"User authenticated: {decoded_token['uid']}")
        return decoded_token
    except IndexError:
        logging.error("Malformed authorization header")
        raise HTTPException(status_code=401, detail="Invalid authorization header format")
    except auth.InvalidIdTokenError:
        logging.error("Invalid authentication token")
        raise HTTPException(status_code=401, detail="Invalid authentication token")
    except Exception as e:
        logging.error(f"Authentication error: {str(e)}")
        raise HTTPException(status_code=401, detail="Authentication error")

async def get_authenticated_user(request: Request) -> Dict[str, Any]:
    """
    Authenticate the user from the request's Authorization header.

    Args:
        request (Request): The FastAPI request object.

    Returns:
        Dict[str, Any]: The authenticated user's information.

    Raises:
        HTTPException: If authentication fails.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    token = auth_header.split("Bearer ")[1]
    try:
        return auth.verify_id_token(token)
    except auth.InvalidIdTokenError:
        raise HTTPException(status_code=401, detail="Invalid authentication token")

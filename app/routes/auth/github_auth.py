from fastapi import HTTPException, Request, APIRouter
from fastapi.responses import JSONResponse
from firebase_admin import db, auth
from fastapi.responses import RedirectResponse, JSONResponse
from firebase_admin import db, auth

from app.config import FRONTEND_URL, GITHUB_ACCESS_TOKEN_URL, GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET, GITHUB_REDIRECT_URI, GITHUB_USER_URL

import httpx
import logging

router = APIRouter()

@router.get("/login/callback")
async def github_callback(request: Request):
    logging.info("GitHub callback endpoint accessed")
    code = request.query_params.get("code")
    firebase_token = request.query_params.get("state")
    
    if not code or not firebase_token:
        logging.warning("Missing authorization code or Firebase token")
        raise HTTPException(status_code=400, detail="Missing required parameters")

    try:
        # Verify the Firebase token
        decoded_token = auth.verify_id_token(firebase_token)
        user_id = decoded_token['uid']

        # Exchange the code for a GitHub access token
        token_url = GITHUB_ACCESS_TOKEN_URL
        headers = {"Accept": "application/json"}
        data = {
            "client_id": GITHUB_CLIENT_ID,
            "client_secret": GITHUB_CLIENT_SECRET,
            "code": code,
            "redirect_uri": GITHUB_REDIRECT_URI,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(token_url, headers=headers, data=data)

        if response.status_code != 200:
            logging.error(f"Failed to exchange code for access token: {response.text}")
            raise HTTPException(status_code=400, detail="Failed to exchange code for access token")

        token_data = response.json()
        access_token = token_data.get("access_token")

        if not access_token:
            logging.error("Failed to obtain GitHub access token")
            raise HTTPException(status_code=400, detail="Failed to obtain GitHub access token")

        # Fetch GitHub user data
        user_url = GITHUB_USER_URL
        headers = {
            "Authorization": f"token {access_token}",
            "Accept": "application/vnd.github.v3+json",
        }

        async with httpx.AsyncClient() as client:
            user_response = await client.get(user_url, headers=headers)

        if user_response.status_code != 200:
            logging.error(f"Failed to fetch GitHub user data: {user_response.text}")
            raise HTTPException(status_code=400, detail="Failed to fetch GitHub user data")

        user_data = user_response.json()
        github_username = user_data.get('login')

        # Store GitHub token and username in Firebase
        logging.info(f"Storing GitHub token for user: {user_id}")
        ref = db.reference('users')
        ref.child(user_id).update({
            'github_token': access_token,
            'github_code': code,
            'github_username': github_username
        })

        frontend_url = f"{FRONTEND_URL}/github-linked?username={github_username}"
        logging.info(f"Redirecting to: {frontend_url}")
        return RedirectResponse(url=frontend_url)

    except Exception as e:
        logging.error(f"Error in github_callback: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
    
@router.get("/github/status")
async def get_github_status(request: Request):
    try:
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            logging.warning("Missing authentication token")
            raise HTTPException(status_code=401, detail="Missing authentication token")
        
        token = auth_header.split("Bearer ")[1]
        current_user = auth.verify_id_token(token)
        user_id = current_user['uid']
        
        ref = db.reference(f'users/{user_id}')
        user_data = ref.get()
        
        if user_data and 'github_username' in user_data:
            return JSONResponse(content={"linked": True, "username": user_data['github_username']})
        else:
            return JSONResponse(content={"linked": False})
    except Exception as e:
        logging.error(f"Error in get_github_status: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
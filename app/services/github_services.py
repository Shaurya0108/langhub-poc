from app.config import GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET, GITHUB_ACCESS_TOKEN_URL, GITHUB_USER_URL
from firebase_admin import db
import logging
import httpx
from typing import List, Dict
from fastapi import HTTPException

async def refresh_github_token(user_id: str) -> str | None:
    """
    Refresh the GitHub access token for a given user.

    This function retrieves the user's GitHub code from Firebase,
    uses it to request a new access token from GitHub, and updates
    the user's record in Firebase with the new token.

    Args:
        user_id (str): The ID of the user whose token needs to be refreshed.

    Returns:
        str | None: The new access token if successful, None otherwise.
    """
    ref = db.reference(f'users/{user_id}')
    user_data = ref.get()
    
    if not user_data or 'github_code' not in user_data:
        logging.warning(f"No GitHub code found for user {user_id}")
        return None

    token_url = GITHUB_ACCESS_TOKEN_URL
    headers = {"Accept": "application/json"}
    data = {
        "client_id": GITHUB_CLIENT_ID,
        "client_secret": GITHUB_CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": user_data['github_code']
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(token_url, headers=headers, data=data)

    if response.status_code == 200:
        token_data = response.json()
        new_access_token = token_data.get("access_token")

        if new_access_token:
            ref.update({
                'github_token': new_access_token
            })
            logging.info(f"Successfully refreshed GitHub token for user {user_id}")
            return new_access_token
    
    logging.error(f"Failed to refresh GitHub token for user {user_id}")
    return None

async def fetch_github_repos(access_token: str, page: int, per_page: int) -> List[Dict]:
    """
    Fetch a page of GitHub repositories for a user.

    Args:
        access_token (str): The GitHub access token.
        page (int): The page number to fetch.
        per_page (int): The number of repositories per page.

    Returns:
        List[Dict]: A list of dictionaries containing repository information.

    Raises:
        HTTPException: If the GitHub API request fails.
    """
    repos_url = f"{GITHUB_USER_URL}/repos?page={page}&per_page={per_page}"
    headers = {
        "Authorization": f"token {access_token}",
        "Accept": "application/vnd.github.v3+json",
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(repos_url, headers=headers)

    if response.status_code == 200:
        repos = response.json()
        return [{
            'name': repo['name'],
            'private': repo['private'],
            'description': repo['description'] or '',
            'url': repo['html_url'],
            'created_at': repo['created_at'],
            'updated_at': repo['updated_at'],
            'language': repo['language'] or 'Not specified'
        } for repo in repos]
    elif response.status_code == 401:
        raise HTTPException(status_code=401, detail="GitHub token is invalid")
    else:
        logging.error(f"Failed to fetch GitHub repositories: {response.text}")
        raise HTTPException(status_code=400, detail="Failed to fetch GitHub repositories")
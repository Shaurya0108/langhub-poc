import logging
from fastapi import HTTPException, Request, APIRouter
from fastapi.responses import JSONResponse
from firebase_admin import db

from app.services.google_services import get_authenticated_user
from app.services.github_services import fetch_github_repos, refresh_github_token

router = APIRouter()

@router.get("/github/repos")
async def get_github_repos(request: Request):
    """
    Fetch all GitHub repositories for the authenticated user.

    Args:
        request (Request): The FastAPI request object.

    Returns:
        JSONResponse: A JSON response containing the list of repositories.

    Raises:
        HTTPException: If an error occurs during the process.
    """
    try:
        user = await get_authenticated_user(request)
        user_id = user['user_id']
        
        logging.info(f"Fetching GitHub repos for user: {user_id}")
        ref = db.reference(f'users/{user_id}')
        user_data = ref.get()
        
        if not user_data or 'github_token' not in user_data:
            logging.warning(f"No GitHub account linked for user: {user_id}")
            return JSONResponse(content={"message": "GitHub account not linked"}, status_code=404)
        
        access_token = user_data['github_token']
        logging.info(f"Access token retrieved for user: {user_id}")
        
        all_repos = []
        page = 1
        per_page = 100  # Maximum allowed by GitHub API

        while True:
            try:
                repos = await fetch_github_repos(access_token, page, per_page)
            except HTTPException as e:
                if e.status_code == 401:
                    logging.info("Token expired, attempting to refresh")
                    new_access_token = await refresh_github_token(user_id)
                    if new_access_token:
                        access_token = new_access_token
                        repos = await fetch_github_repos(access_token, page, per_page)
                    else:
                        logging.error("Failed to refresh GitHub token")
                        return JSONResponse(content={"message": "GitHub token is invalid. Please re-authenticate."}, status_code=401)
                else:
                    raise

            all_repos.extend(repos)
            if len(repos) < per_page:
                break
            page += 1

        repo_length = len(all_repos)
        ref.update({
            'number_of_repos': repo_length
        })

        logging.info(f"Successfully fetched {repo_length} repos for user: {user_id}")
        return JSONResponse(content={"repos": all_repos})
    except Exception as e:
        logging.error(f"Error in get_github_repos: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
from datetime import datetime
from app.services.google_services import get_authenticated_user
from httpx import AsyncClient
from fastapi import HTTPException, Request, Depends, File, Form, APIRouter, UploadFile
from fastapi.responses import JSONResponse
from firebase_admin import db
from app.services.repository_services import get_repo_files_content, get_repo_structure, process_zip_contents
from app.services.s3_manager import S3Manager
from app.routes.auth import google_auth

import logging
import uuid
import base64

router = APIRouter()

@router.post("/upload-repo")
async def upload_repo(
    request: Request,
    file: UploadFile = File(...),
    repo_type: str = Form(...),
    repo_name: str = Form(...)
):
    """
    Upload a repository (currently supports zip files only).

    Args:
        request (Request): The FastAPI request object.
        file (UploadFile): The uploaded file.
        repo_type (str): The type of repository (e.g., "zip").
        repo_name (str): The name of the repository.

    Returns:
        JSONResponse: Information about the uploaded repository.

    Raises:
        HTTPException: If an error occurs during the upload process.
    """
    try:
        current_user = await get_authenticated_user(request)
        user_id = current_user['uid']

        logging.info(f"Processing upload for user: {user_id}, repo_name: {repo_name}, repo_type: {repo_type}")

        if repo_type != "zip":
            return JSONResponse(status_code=400, content={"message": f"Unsupported repo_type: {repo_type}"})

        repo_hash = str(uuid.uuid4())
        s3_manager = S3Manager(repo_hash=repo_hash, repo_name=repo_name)

        try:
            file_content = await file.read()
            s3_url = await s3_manager.upload_zip_file(file_content)
            logging.info(f"Uploaded zip file to S3: {s3_url}")
        except Exception as e:
            logging.error(f"An error occurred when uploading to S3: {e}")
            return JSONResponse(status_code=500, content={"message": f"Failed to upload to S3: {str(e)}"})

        try:
            raw_contents = await s3_manager.get_and_unzip_repo()
            logging.info(f"Retrieved and unzipped contents from S3")
        except Exception as e:
            logging.error(f"An error occurred when retrieving from S3: {e}")
            return JSONResponse(status_code=500, content={"message": f"Failed to retrieve from S3: {str(e)}"})

        contents, ignored_files = await process_zip_contents(raw_contents)

        # Store the repo information in Firebase
        ref = db.reference(f'users/{user_id}/repos')
        ref.push({
            'repo_name': repo_name,
            'repo_hash': repo_hash,
            'upload_date': datetime.now().isoformat(),
            'type': 'zip',
            'link': s3_url
        })

        response_data = {
            "success": True,
            "message": f"Successfully uploaded and processed {repo_type} repo: {repo_name}",
            "contents": contents,
            "ignored_files": ignored_files,
            "repo_hash": repo_hash,
            "s3_url": s3_url
        }
        logging.info(f"Sending response for uploaded repo: {response_data}")
        return JSONResponse(status_code=200, content=response_data)
    except Exception as e:
        logging.error(f"Error processing uploaded repo: {str(e)}")
        return JSONResponse(status_code=500, content={"message": f"Internal server error: {str(e)}"})

@router.get("/repos/{repo_name}/files")
async def get_repo_files(repo_name: str, request: Request):
    """
    Get the files of a GitHub repository.

    Args:
        repo_name (str): The name of the repository.
        request (Request): The FastAPI request object.

    Returns:
        JSONResponse: The files in the repository.

    Raises:
        HTTPException: If an error occurs while fetching the files.
    """
    try:
        access_token = request.session.get("access_token")

        if not access_token:
            raise HTTPException(status_code=401, detail="Not authenticated")

        async with AsyncClient() as client:
            url = f"https://api.github.com/repos/{request.session['user']['login']}/{repo_name}/contents"
            files_response = await client.get(
                url,
                headers={"Authorization": f"Bearer {access_token}"}
            )

            if files_response.status_code == 404:
                raise HTTPException(status_code=404, detail="Repository not found or no access")

            logging.info(f"\nThe file response: {files_response.json}\n")

            return files_response.json()
    except Exception as e:
        logging.error(f"An error occurred in get repo files: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/repos/{repo_name}/structure")
async def repo_structure(repo_name: str, request: Request):
    """
    Get the structure of a GitHub repository.

    Args:
        repo_name (str): The name of the repository.
        request (Request): The FastAPI request object.

    Returns:
        Dict: The structure of the repository.

    Raises:
        HTTPException: If the user is not authenticated.
    """
    access_token = request.session.get("access_token")
    user = request.session.get("user")
    if not access_token or not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    return await get_repo_structure(repo_name, user['login'], access_token)

@router.get("/repos/{repo_name}/files/content")
async def repo_files_content(repo_name: str, current_user: dict = Depends(google_auth.get_current_user)):
    """
    Get the content of files in a GitHub repository.

    Args:
        repo_name (str): The name of the repository.
        current_user (dict): The current authenticated user.

    Returns:
        Dict: The contents of the repository files and ignored files.

    Raises:
        HTTPException: If an error occurs while fetching the file contents.
    """
    try:
        user_id = current_user['uid']
        ref = db.reference(f'users/{user_id}')
        user_data = ref.get()
        
        if not user_data or 'github_token' not in user_data:
            raise HTTPException(status_code=401, detail="GitHub account not linked")
        
        access_token = user_data['github_token']
        github_username = user_data['github_username']

        contents, ignored_files = await get_repo_files_content(repo_name, github_username, access_token)

        # Check if the repo exists in Firebase
        ref = db.reference(f'users/{user_id}/repos')
        repos = ref.get() or {}

        existing_repo_id = next((repo_id for repo_id, repo_data in repos.items() if repo_data.get('repo_name') == repo_name), None)

        if existing_repo_id:
            # Update the existing repo
            ref.child(existing_repo_id).update({
                'upload_date': datetime.now().isoformat()
            })
            logging.info(f"Updated existing repo: {repo_name} for user: {user_id}")
        else:
            # Add new repo
            repo_hash = str(uuid.uuid4())
            new_repo = {
                'repo_name': repo_name,
                'repo_hash': repo_hash,
                'upload_date': datetime.now().isoformat(),
                'type': 'github',
                'link': f'https://api.github.com/repos/{github_username}/{repo_name}'
            }
            ref.push(new_repo)
            logging.info(f"Added new repo: {repo_name} for user: {user_id}")

        return {"contents": contents, "ignored_files": ignored_files}
    except Exception as e:
        logging.error(f"Error in repo_files_content: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/api/save-file")
async def save_file(request: Request, current_user: dict = Depends(google_auth.get_current_user)):
    """
    Save a file to a GitHub repository.

    Args:
        request (Request): The FastAPI request object.
        current_user (dict): The current authenticated user.

    Returns:
        JSONResponse: A success message if the file is saved successfully.

    Raises:
        HTTPException: If an error occurs while saving the file.
    """
    try:
        data = await request.json()
        repo = data.get('repo')
        path = data.get('path')
        content = data.get('content')
        message = data.get('message', f"Update {path}")

        if not repo or not path or not content:
            raise HTTPException(status_code=400, detail="Missing required parameters")

        user_id = current_user['uid']
        ref = db.reference(f'users/{user_id}')
        user_data = ref.get()

        if not user_data or 'github_token' not in user_data:
            raise HTTPException(status_code=401, detail="GitHub account not linked")

        github_token = user_data['github_token']
        github_username = user_data['github_username']

        url = f"https://api.github.com/repos/{github_username}/{repo}/contents/{path}"

        headers = {
            "Authorization": f"token {github_token}",
            "Accept": "application/vnd.github.v3+json"
        }

        async with AsyncClient() as client:
            response = await client.get(url, headers=headers)
            if response.status_code == 404:
                raise HTTPException(status_code=404, detail="File not found in the repository")
            elif response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail="Failed to get file information from GitHub")
            
            current_file = response.json()
            sha = current_file['sha']

        update_data = {
            "message": message,
            "content": base64.b64encode(content.encode()).decode(),
            "sha": sha
        }

        async with AsyncClient() as client:
            response = await client.put(url, headers=headers, json=update_data)
            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail="Failed to update file on GitHub")

        return JSONResponse(content={"message": "File updated successfully"}, status_code=200)

    except Exception as e:
        logging.error(f"Error in save_file: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    
@router.get("/past-repo")
async def past_repo(current_user: dict = Depends(google_auth.get_current_user)):
    """
    Get the list of past repositories for the current user.

    Args:
        current_user (dict): The current authenticated user.

    Returns:
        JSONResponse: A list of past repositories.

    Raises:
        HTTPException: If an error occurs while fetching the repositories.
    """
    try:
        user_id = current_user['uid']
        logging.info(f"Fetching past repositories for user: {user_id}")

        ref = db.reference(f'users/{user_id}/repos')
        repos = ref.get()

        if repos is None:
            logging.info(f"No repositories found for user: {user_id}")
            return JSONResponse(content={"repos": []})

        repo_list = [
            {
                "id": repo_id,
                "name": repo_data.get('repo_name'),
                "hash": repo_data.get('repo_hash'),
                "upload_date": repo_data.get('upload_date'),
                "type": repo_data.get('type')
            }
            for repo_id, repo_data in repos.items()
        ]

        repo_list.sort(key=lambda x: x['upload_date'], reverse=True)

        logging.info(f"Successfully retrieved {len(repo_list)} repositories for user: {user_id}")
        return JSONResponse(content={"repos": repo_list})

    except Exception as e:
        logging.error(f"Error in past_repo: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.delete("/delete-repo/{repo_hash}")
async def delete_repo(repo_hash: str, current_user: dict = Depends(google_auth.get_current_user)):
    """
    Delete a repository for the current user.

    Args:
        repo_hash (str): The hash of the repository to delete.
        current_user (dict): The current authenticated user.

    Returns:
        Dict: A success message if the repository is deleted successfully.

    Raises:
        HTTPException: If an error occurs while deleting the repository.
    """
    try:
        user_id = current_user['uid']
        ref = db.reference(f'users/{user_id}/repos')
        repos = ref.get()

        if repos is None:
            raise HTTPException(status_code=404, detail="No repositories found")

        deleted = False
        for repo_id, repo_data in repos.items():
            if repo_data.get('repo_hash') == repo_hash:
                if repo_data.get('type') == 'zip':
                    try:
                        s3_manager = S3Manager(
                            repo_hash=repo_hash,
                            repo_name=repo_data.get('repo_name')
                        )
                        await s3_manager.delete_zip_file()
                        logging.info(f"Deleted zip file from S3 for repo: {repo_data.get('repo_name')}")
                    except Exception as e:
                        logging.error(f"Failed to delete S3 zip file: {str(e)}")
                        # Even if S3 deletion fails, we'll continue to delete the database entry
                
                # Delete the database entry
                ref.child(repo_id).delete()
                deleted = True
                break

        if not deleted:
            raise HTTPException(status_code=404, detail="Repository not found")

        return {"message": "Repository deleted successfully"}
    except Exception as e:
        logging.error(f"Error in delete_repo: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
from fastapi import HTTPException, Request, APIRouter
from firebase_admin import db, auth

router = APIRouter()

def get_repo_key(user_id: str, repo_name: str) -> str:
    """
    Get the Firebase key for a repository.

    Args:
        user_id (str): The ID of the user.
        repo_name (str): The name of the repository.

    Returns:
        str: The Firebase key for the repository.

    Raises:
        HTTPException: If the repository is not found.
    """
    repos_ref = db.reference(f'users/{user_id}/repos')
    repos = repos_ref.get()
    
    if not repos:
        raise HTTPException(status_code=404, detail="No repositories found")
    
    repo_key = next((key for key, repo in repos.items() if repo['repo_name'] == repo_name), None)
    
    if not repo_key:
        raise HTTPException(status_code=404, detail=f"Repository {repo_name} not found")
    
    return repo_key

def build_tree(nodes, parent_id=None):
    """
    Recursively build a tree structure from flat node data.

    Args:
        nodes (dict): The flat structure of nodes.
        parent_id (str, optional): The ID of the parent node. Defaults to None.

    Returns:
        list: A list of node dictionaries in a tree structure.
    """
    tree = []
    for key, node in nodes.items():
        if node['parent_id'] == parent_id:
            children = build_tree(nodes, node['node_id'])
            node_data = {
                "name": node['name'],
                "id": node['node_id'],
                "children": children,
                "isOpen": True,
                "description": node['description'],
                "createdAt": node['created_at'],
                "lastModified": node['last_modified'],
                "firebaseKey": key
            }
            tree.append(node_data)
    return tree

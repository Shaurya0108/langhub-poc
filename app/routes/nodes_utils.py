from datetime import datetime
import logging
import uuid
from app.services.google_services import get_authenticated_user
from app.services.nodes_service import build_tree, get_repo_key
from fastapi import HTTPException, Request, APIRouter
from fastapi.responses import JSONResponse
from firebase_admin import db

router = APIRouter()

@router.get("/nodes/{repo_name}")
async def get_nodes(repo_name: str, request: Request):
    """
    Get all nodes for a given repository.

    Args:
        repo_name (str): The name of the repository.
        request (Request): The FastAPI request object.

    Returns:
        JSONResponse: The root node containing all child nodes.

    Raises:
        HTTPException: If authentication fails or an error occurs.
    """
    try:
        current_user = get_authenticated_user(request)
        user_id = current_user['uid']
        repo_key = get_repo_key(user_id, repo_name)
        
        nodes = db.reference(f'users/{user_id}/repos/{repo_key}/nodes').get()

        root_node = {
            "name": "Root Node",
            "id": "root",
            "children": [],
            "isOpen": True,
            "description": "This is the root node",
            "createdAt": datetime.utcnow().isoformat(),
            "lastModified": datetime.utcnow().isoformat(),
        }

        logging.info(f"the nodes in firebase are: \n{nodes}")

        if nodes:
            root_node["children"] = build_tree(nodes, parent_id="root")

        logging.info(f"the tree is: \n{root_node}")

        return JSONResponse(status_code=200, content=root_node)

    except Exception as e:
        logging.error(f"Error fetching nodes: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.post("/add-node")
async def add_node(request: Request):
    """
    Add a new node to a repository.

    Args:
        request (Request): The FastAPI request object containing node details.

    Returns:
        JSONResponse: Information about the newly created node.

    Raises:
        HTTPException: If authentication fails or an error occurs.
    """
    try:
        current_user = get_authenticated_user(request)
        user_id = current_user['uid']

        body = await request.json()
        parent_id = body.get('parent_id')
        repo_name = body.get('repo_name')

        node_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().isoformat()
    
        repo_key = get_repo_key(user_id, repo_name)
        
        nodes_ref = db.reference(f'users/{user_id}/repos/{repo_key}/nodes')
        new_node_ref = nodes_ref.push({
            'node_id': node_id,
            'parent_id': parent_id,
            'name': 'New Node',
            'description': 'New node description',
            'created_at': timestamp,
            'last_modified': timestamp
        })

        return JSONResponse(status_code=201, content={
            "message": "Node created successfully",
            "node_id": node_id,
            "firebase_key": new_node_ref.key
        })

    except Exception as e:
        logging.error(f"Error creating node: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.delete("/delete-node/{repo_name}/{node_id}")
async def delete_node(repo_name: str, node_id: str, request: Request):
    """
    Delete a node and all its children from a repository.

    Args:
        repo_name (str): The name of the repository.
        node_id (str): The ID of the node to delete.
        request (Request): The FastAPI request object.

    Returns:
        JSONResponse: A success message.

    Raises:
        HTTPException: If authentication fails or an error occurs.
    """
    try:
        current_user = get_authenticated_user(request)
        user_id = current_user['uid']

        repo_key = get_repo_key(user_id, repo_name)
        
        nodes_ref = db.reference(f'users/{user_id}/repos/{repo_key}/nodes')
        nodes = nodes_ref.get()

        if not nodes:
            raise HTTPException(status_code=404, detail="Node not found")

        def delete_node_and_children(nodes, node_id):
            for key, node in list(nodes.items()):
                if node['node_id'] == node_id:
                    del nodes[key]
                elif node['parent_id'] == node_id:
                    delete_node_and_children(nodes, node['node_id'])

        delete_node_and_children(nodes, node_id)
        nodes_ref.set(nodes)

        return JSONResponse(status_code=200, content={"message": "Node deleted successfully"})

    except Exception as e:
        logging.error(f"Error deleting node: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
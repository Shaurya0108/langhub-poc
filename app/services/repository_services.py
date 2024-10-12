import tempfile
import zipfile
import logging
import os
import chardet
from typing import Dict
from httpx import AsyncClient
from fastapi import HTTPException, UploadFile

# Constants
IGNORED_FILES = {'.DS_Store', 'Thumbs.db', '.gitignore', '.gitattributes', '.gitmodules'}
IGNORED_EXTENSIONS = {'.exe', '.pyc', '.pyo', '.pyd', '.dll', '.so', '.dylib', '.zip', '.tar', '.gz', '.rar', '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.ico', '.svg', '.mp3', '.mp4', '.avi', '.mov', '.pdf'}

# Utility functions
def mask_token(token: str) -> str:
    """
    Mask the access token for logging purposes.

    Args:
        token (str): The access token to mask.

    Returns:
        str: The masked token.
    """
    return f"{token[:4]}...{token[-4:]}" if token else "None"

def should_ignore_file(file_path: str) -> bool:
    """
    Determine if a file should be ignored based on its name or extension.

    Args:
        file_path (str): The file path to check.

    Returns:
        bool: True if the file should be ignored, False otherwise.
    """
    file_name = os.path.basename(file_path)
    return (
        file_name in IGNORED_FILES or
        any(file_name.endswith(ext) for ext in IGNORED_EXTENSIONS) or
        '/.git/' in file_path or
        file_path.startswith('.git/')
    )

def is_binary_string(bytes_data: bytes) -> bool:
    """
    Check if the given bytes data is binary.

    Args:
        bytes_data (bytes): The data to check.

    Returns:
        bool: True if the data is binary, False otherwise.
    """
    textchars = bytearray({7,8,9,10,12,13,27} | set(range(0x20, 0x100)) - {0x7f})
    return bool(bytes_data.translate(None, textchars))

def decode_file_content(content: bytes) -> str:
    """
    Attempt to decode file content to UTF-8.

    Args:
        content (bytes): The content to decode.

    Returns:
        str: The decoded content, or None if decoding fails.
    """
    if is_binary_string(content):
        return None
    
    try:
        return content.decode('utf-8')
    except UnicodeDecodeError:
        encoding = chardet.detect(content)['encoding']
        if encoding:
            try:
                return content.decode(encoding)
            except UnicodeDecodeError:
                return None
    return None

# GitHub repository operations
async def get_repo_structure(repo_name: str, user_login: str, access_token: str) -> Dict:
    """
    Fetch repository structure from GitHub.

    Args:
        repo_name (str): The name of the repository.
        user_login (str): The GitHub username.
        access_token (str): The GitHub access token.

    Returns:
        Dict: The repository structure.

    Raises:
        HTTPException: If fetching the structure fails.
    """
    logging.info(f"Getting structure for repo: {repo_name}, user: {user_login}")
    async with AsyncClient() as client:
        url = f"https://api.github.com/repos/{user_login}/{repo_name}/contents"
        structure = await fetch_structure(client, url, access_token)
        if structure is None:
            raise HTTPException(status_code=404, detail=f"Failed to fetch structure for repository: {repo_name}")

        return {"name": repo_name, "type": "repository", "contents": structure}

async def fetch_structure(client: AsyncClient, url: str, access_token: str, path: str = "") -> list:
    """
    Recursively fetch the structure of a repository or directory.

    Args:
        client (AsyncClient): The HTTP client.
        url (str): The URL to fetch from.
        access_token (str): The GitHub access token.
        path (str): The current path in the repository.

    Returns:
        list: The structure of the repository or directory.
    """
    logging.info(f"Fetching structure from {url}")
    logging.info(f"Using access token: {mask_token(access_token)}")
    headers = {"Authorization": f"Bearer {access_token}"}
    logging.info(f"Request headers: {headers}")

    try:
        response = await client.get(url, headers=headers)
        logging.info(f"Response status code: {response.status_code}")
        logging.info(f"Response headers: {response.headers}")

        if response.status_code != 200:
            logging.error(f"Failed to fetch contents from {url}. Status code: {response.status_code}")
            logging.error(f"Response content: {response.text}")
            return None

        contents = response.json()
        result = []

        for item in contents:
            if item['type'] == 'file' and not should_ignore_file(item['name']):
                result.append({
                    "type": "file",
                    "name": item['name'],
                    "path": f"{path}/{item['name']}".lstrip('/'),
                    "size": item['size']
                })
            elif item['type'] == 'dir':
                sub_contents = await fetch_structure(client, item['url'], access_token, f"{path}/{item['name']}")
                if sub_contents is not None:
                    result.append({
                        "type": "directory",
                        "name": item['name'],
                        "path": f"{path}/{item['name']}".lstrip('/'),
                        "contents": sub_contents
                    })

        return result
    except Exception as e:
        logging.error(f"Error fetching structure from {url}: {str(e)}")
        return None

async def get_repo_files_content(repo_name: str, github_username: str, access_token: str) -> tuple:
    """
    Fetch repository contents from GitHub.

    Args:
        repo_name (str): The name of the repository.
        github_username (str): The GitHub username.
        access_token (str): The GitHub access token.

    Returns:
        tuple: A tuple containing the repository contents and ignored files.

    Raises:
        HTTPException: If fetching the contents fails.
    """
    async with AsyncClient() as client:
        url = f"https://api.github.com/repos/{github_username}/{repo_name}/contents"
        contents, ignored_files = await fetch_contents(client, url, access_token)
        if contents is None:
            raise HTTPException(status_code=404, detail=f"Failed to fetch contents for repository: {repo_name}")

        return contents, ignored_files

async def fetch_contents(client: AsyncClient, url: str, access_token: str) -> tuple:
    """
    Recursively fetch the contents of a repository or directory.

    Args:
        client (AsyncClient): The HTTP client.
        url (str): The URL to fetch from.
        access_token (str): The GitHub access token.

    Returns:
        tuple: A tuple containing the contents and ignored files.
    """
    ignored_files = []
    if url is None:
        logging.error(f"Received None URL in fetch_contents")
        return None, ignored_files
    try:
        response = await client.get(url, headers={"Authorization": f"Bearer {access_token}"})
        if response.status_code != 200:
            logging.error(f"Failed to fetch contents from {url}. Status code: {response.status_code}")
            return None, ignored_files
        contents = response.json()
        result = {}
        for item in contents:
            if item['type'] == 'file':
                if should_ignore_file(item['name']):
                    ignored_files.append(item['name'])
                    logging.info(f"Ignored file: {item['name']}")
                    continue
                file_url = item.get('download_url')
                if file_url:
                    file_content_response = await client.get(file_url)
                    try:
                        # Try to decode as UTF-8
                        content = file_content_response.content.decode('utf-8')
                        result[item['name']] = content
                    except UnicodeDecodeError:
                        # If decoding fails, it's a binary file
                        ignored_files.append(item['name'])
                        logging.warning(f"Ignored binary file: {item['name']}")
                else:
                    logging.warning(f"No download URL for file {item['name']} in {url}")
            elif item['type'] == 'dir':
                sub_contents, sub_ignored = await fetch_contents(client, item.get('url'), access_token)
                if sub_contents is not None:
                    result[item['name']] = sub_contents
                ignored_files.extend(sub_ignored)
        return result, ignored_files
    except Exception as e:
        logging.error(f"Error fetching contents from {url}: {str(e)}")
        return None, ignored_files

async def get_repo_code(repo_content: Dict[str, bytes], should_ignore_file) -> Dict[str, str]:
    """
    Extract code files from repository content.

    Args:
        repo_content (Dict[str, bytes]): A dictionary of file paths and their content.
        should_ignore_file (function): A function to determine if a file should be ignored.

    Returns:
        Dict[str, str]: A dictionary of code file paths and their decoded content.
    """
    if repo_content:
        # Filter the dictionary to include only files that should not be ignored
        filtered_repo_content = {filename: content for filename, content in repo_content.items() if not should_ignore_file(filename)}
        
        # Decode the file contents to string (assuming UTF-8) after filtering
        decoded_repo_content = {}
        for filename, content in filtered_repo_content.items():
            try:
                # Attempt to decode the content as UTF-8
                decoded_repo_content[filename] = content.decode('utf-8')
            except UnicodeDecodeError:
                # Handle cases where the content can't be decoded (e.g., binary files)
                decoded_repo_content[filename] = None  # Or handle appropriately (log or skip)
        
        return decoded_repo_content
    else:
        return {}

# File processing functions
def process_directory(directory: str) -> Dict:
    """
    Process a directory and return its structure with file contents.

    Args:
        directory (str): The path to the directory to process.

    Returns:
        Dict: A dictionary representing the directory structure with file contents.
    """
    structure = {}
    for root, dirs, files in os.walk(directory):
        current = structure
        path = os.path.relpath(root, directory)
        if path != '.':
            parts = path.split(os.sep)
            for part in parts:
                current = current.setdefault(part, {})
        for file in files:
            if not file.startswith('.'):  # Ignore hidden files
                file_path = os.path.join(root, file)
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    try:
                        content = f.read()
                        current[file] = content
                    except UnicodeDecodeError:
                        # For binary files, just store the file name
                        current[file] = "Binary file"
    return structure

def process_zip_file(zip_file: UploadFile) -> Dict:
    """
    Process an uploaded zip file and return its structure with file contents.

    Args:
        zip_file (UploadFile): The uploaded zip file.

    Returns:
        Dict: A dictionary representing the zip file's structure with file contents.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        zip_path = os.path.join(temp_dir, zip_file.filename)
        
        # Save the uploaded file
        with open(zip_path, "wb") as buffer:
            buffer.write(zip_file.file.read())
        
        # Extract the zip file
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
        
        # Process the extracted files
        file_structure = process_directory(temp_dir)
        
    return file_structure

def process_uploaded_files(directory: str) -> tuple:
    """
    Process uploaded files in a directory and return their contents and ignored files.

    Args:
        directory (str): The path to the directory containing uploaded files.

    Returns:
        tuple: A tuple containing the file contents and a list of ignored files.
    """
    contents = {}
    ignored_files = []
    max_file_size = 1024 * 1024  # 1 MB

    def add_to_structure(structure, path_parts, content):
        if len(path_parts) == 1:
            structure[path_parts[0]] = content
        else:
            if path_parts[0] not in structure:
                structure[path_parts[0]] = {}
            add_to_structure(structure[path_parts[0]], path_parts[1:], content)

    for root, _, files in os.walk(directory):
        for file in files:
            file_path = os.path.join(root, file)
            relative_path = os.path.relpath(file_path, directory)
            
            # Remove the top-level directory from the path
            path_parts = relative_path.split(os.sep)
            if len(path_parts) > 1:
                path_parts = path_parts[1:]
            
            if os.path.getsize(file_path) > max_file_size:
                ignored_files.append(os.path.join(*path_parts))
                continue

            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    file_content = f.read()
                add_to_structure(contents, path_parts, file_content)
            except UnicodeDecodeError:
                ignored_files.append(os.path.join(*path_parts))

    return contents, ignored_files

async def process_zip_contents(raw_contents: Dict[str, bytes]) -> tuple:
    """
    Process the contents of a zip file.

    Args:
        raw_contents (Dict[str, bytes]): The raw contents of the zip file.

    Returns:
        tuple: A tuple containing the processed contents and ignored files.
    """
    contents = {}
    ignored_files = []
    for name, content in raw_contents.items():
        if should_ignore_file(name):
            ignored_files.append(name)
        else:
            decoded_content = decode_file_content(content)
            if decoded_content is not None:
                path_parts = name.split('/')
                current = contents
                for part in path_parts[:-1]:
                    if part not in current:
                        current[part] = {}
                    current = current[part]
                current[path_parts[-1]] = decoded_content
            else:
                ignored_files.append(name)
    return contents, ignored_files

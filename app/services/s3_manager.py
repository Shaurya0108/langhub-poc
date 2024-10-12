import io
import json
import logging
import zipfile
import boto3
from datetime import datetime
from typing import Dict, Optional
from botocore.exceptions import ClientError
from aiobotocore.session import get_session

class S3Manager:
    """
    A class to manage S3 operations for a specific repository.
    """
    def __init__(
        self,
        repo_hash: str,
        repo_name: str,
        region_name: str = 'us-east-1'
    ):
        """
        Initialize the S3Manager.

        Args:
            repo_hash (str): The hash of the repository.
            repo_name (str): The name of the repository.
            region_name (str): The AWS region name. Defaults to 'us-east-1'.
        """
        self.bucket_name = '' # s3 bucket
        self.repo_hash = repo_hash
        self.repo_name = repo_name
        self.region_name = region_name
        self.s3_client = boto3.client('s3', region_name=region_name)

    def _construct_s3_path(self, file_path: str) -> str:
        """
        Construct the S3 path for a given file.

        Args:
            file_path (str): The file path within the repository.

        Returns:
            str: The full S3 path.
        """
        return f"{self.repo_hash}/{self.repo_name}/{file_path}"

    def _generate_s3_url(self, file_path: str) -> str:
        """
        Generate the S3 URL for a given file.

        Args:
            file_path (str): The file path within the repository.

        Returns:
            str: The full S3 URL.
        """
        s3_path = self._construct_s3_path(file_path)
        return f"https://{self.bucket_name}.s3.{self.region_name}.amazonaws.com/{s3_path}"

    async def upload_zip_file(self, zip_file) -> str:
        """
        Upload a zip file to S3.

        Args:
            zip_file: The zip file to upload.

        Returns:
            str: The S3 URL of the uploaded zip file.

        Raises:
            ClientError: If the upload fails.
        """
        session = get_session()
        async with session.create_client('s3', region_name=self.region_name) as s3_client:
            try:
                s3_path = self._construct_s3_path(f"{self.repo_name}.zip")
                await s3_client.put_object(
                    Bucket=self.bucket_name,
                    Key=s3_path,
                    Body=zip_file
                )
                logging.info(f"Uploaded zip file to S3: {s3_path}")
                return self._generate_s3_url(f"{self.repo_name}.zip")
            except ClientError as e:
                logging.error(f"Failed to upload zip file to S3: {e}")
                raise

    async def apply_changes(self, changes: Dict[str, str]):
        """
        Apply changes to files in S3.

        Args:
            changes (Dict[str, str]): A dictionary mapping file paths to their new content.
        """
        session = get_session()
        async with session.create_client('s3', region_name=self.region_name) as s3_client:
            for file_path, content in changes.items():
                s3_file_path = self._construct_s3_path(file_path)
                await s3_client.put_object(
                    Bucket=self.bucket_name,
                    Key=s3_file_path,
                    Body=content.encode('utf-8')
                )

    async def add_json_object(self, json_data: dict, path: str = "plan"):
        """
        Add a JSON object to S3.

        Args:
            json_data (dict): The JSON data to add.
            path (str): The path where to add the JSON object. Defaults to "plan".
        """
        session = get_session()
        async with session.create_client('s3', region_name=self.region_name) as s3_client:
            s3_file_path = self._construct_s3_path(path)
            json_body = json.dumps(json_data).encode('utf-8')
            await s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_file_path,
                Body=json_body
            )
            logging.info(f"Added JSON object to '{s3_file_path}'.")

    async def fetch_repo_at_timestamp(self, timestamp: str) -> Dict[str, str]:
        """
        Fetch the repository state at a specific timestamp.

        Args:
            timestamp (str): The timestamp in ISO format.

        Returns:
            Dict[str, str]: A dictionary mapping file paths to their content.
        """
        timestamp_dt = datetime.fromisoformat(timestamp)
        repo_state = {}
        session = get_session()
        async with session.create_client('s3', region_name=self.region_name) as s3_client:
            paginator = s3_client.get_paginator('list_object_versions')
            async for page in paginator.paginate(Bucket=self.bucket_name):
                versions = page.get('Versions', [])
                for version in versions:
                    file_path = version['Key']
                    if not file_path.startswith(f"{self.repo_hash}/{self.repo_name}/"):
                        continue
                    version_last_modified = version['LastModified']

                    if version_last_modified <= timestamp_dt:
                        if file_path not in repo_state or repo_state[file_path]['LastModified'] < version_last_modified:
                            repo_state[file_path] = {
                                'VersionId': version['VersionId'],
                                'LastModified': version_last_modified
                            }

            result = {}
            for file_path, version_info in repo_state.items():
                response = await s3_client.get_object(
                    Bucket=self.bucket_name,
                    Key=file_path,
                    VersionId=version_info['VersionId']
                )
                result[file_path] = await response['Body'].read()

        logging.info(f"Fetched repository state as of '{timestamp}'.")
        return result

    async def get_plan(self, timestamp: str) -> Optional[dict]:
        """
        Get the plan at or before a specific timestamp.

        Args:
            timestamp (str): The timestamp in ISO format.

        Returns:
            Optional[dict]: The plan as a dictionary, or None if not found.
        """
        timestamp_dt = datetime.fromisoformat(timestamp)
        plan_path = self._construct_s3_path("plan")
        best_version = None

        session = get_session()
        async with session.create_client('s3', region_name=self.region_name) as s3_client:
            paginator = s3_client.get_paginator('list_object_versions')
            async for page in paginator.paginate(Bucket=self.bucket_name, Prefix=plan_path):
                versions = page.get('Versions', [])
                for version in versions:
                    version_last_modified = version['LastModified']
                    if version_last_modified <= timestamp_dt:
                        if best_version is None or version_last_modified > best_version['LastModified']:
                            best_version = version

            if best_version:
                response = await s3_client.get_object(
                    Bucket=self.bucket_name,
                    Key=plan_path,
                    VersionId=best_version['VersionId']
                )
                plan_content = await response['Body'].read()
                logging.info(f"Fetched plan as of '{timestamp}'.")
                return json.loads(plan_content.decode('utf-8'))

        logging.warning(f"No plan found before or on '{timestamp}'.")
        return None

    def upload_json_object(self, json_data: str):
        """
        Upload a JSON object to S3.

        Args:
            json_data (str): The JSON data to upload.
        """
        s3_file_path = f"{self.repo_hash}/plan.json"
        json_body = json.dumps(json_data).encode('utf-8')
        self.s3_client.put_object(
            Bucket=self.bucket_name,
            Key=s3_file_path,
            Body=json_body
        )
        logging.info(f"Added JSON object to '{s3_file_path}'.")

    def get_and_unzip_repo(self, timestamp: str) -> Optional[Dict[str, bytes]]:
        """
        Retrieve and unzip the repository at or before a specific timestamp.

        Args:
            timestamp (str): The timestamp in ISO format.

        Returns:
            Optional[Dict[str, bytes]]: A dictionary mapping file names to their content as bytes,
                                        or None if not found.

        Raises:
            ClientError: If retrieval or unzipping fails.
        """
        timestamp_dt = datetime.fromisoformat(timestamp)
        s3_path = self._construct_s3_path(f"{self.repo_name}.zip")
        best_version = None

        # Paginate through the versions of the repo zip file
        paginator = self.s3_client.get_paginator('list_object_versions')
        for page in paginator.paginate(Bucket=self.bucket_name, Prefix=s3_path):
            versions = page.get('Versions', [])
            for version in versions:
                version_last_modified = version['LastModified']
                if version_last_modified <= timestamp_dt:
                    if best_version is None or version_last_modified > best_version['LastModified']:
                        best_version = version

        if best_version:
            # Fetch the zip file content for the selected version
            try:
                response = self.s3_client.get_object(
                    Bucket=self.bucket_name,
                    Key=s3_path,
                    VersionId=best_version['VersionId']
                )
                zip_content = response['Body'].read()

                # Unzip the content and return the file mapping
                with io.BytesIO(zip_content) as zip_buffer:
                    with zipfile.ZipFile(zip_buffer) as zip_file:
                        return {name: zip_file.read(name) for name in zip_file.namelist() if not name.endswith('/')}
            except ClientError as e:
                logging.error(f"Failed to retrieve and unzip file from S3 at or before '{timestamp}': {e}")
                raise
        else:
            logging.warning(f"No zip file found before or on '{timestamp}'.")
            return None

    async def delete_zip_file(self) -> None:
        """
        Delete the zip file from S3.

        Raises:
            Exception: If deletion fails.
        """
        session = get_session()
        async with session.create_client('s3', region_name=self.region_name) as s3_client:
            try:
                s3_path = self._construct_s3_path(f"{self.repo_name}.zip")
                await s3_client.delete_object(
                    Bucket=self.bucket_name,
                    Key=s3_path
                )
                logging.info(f"Deleted zip file from S3: {s3_path}")
            except Exception as e:
                logging.error(f"Failed to delete zip file from S3: {e}")
                raise
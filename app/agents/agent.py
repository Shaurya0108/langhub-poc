from datetime import datetime
import json
import logging
from sqlite3 import Timestamp
from fastapi import APIRouter, HTTPException, Depends, Request
from app.agents.coder.coder import CoderAgent
from app.agents.executer.executer import ExecuterAgent
from app.agents.explorer.explorer import ExplorerAgent
from app.llm.llm import LLM
from typing import List, Dict
import os
import io
import zipfile
from app.agents.planner.planner import PlannerAgent
from app.services.repository_services import get_repo_code, get_repo_structure, get_repo_files_content
from app.llm.llm import LLM
from app.services.s3_manager import S3Manager

class AgentOrchestrator:
    def __init__(self, provider: str, model: str, api_key: str, api_base_url: str = None):
        self.llm = LLM(provider, model, api_key, api_base_url)
        # self.project_dir = "/cloned_repos"  # Replace with your actual projects directory

    def generate_sequence(self, prompt: str) -> List[str]:
        # Placeholder for the Planner logic
        # This method should return a sequence of tasks based on the prompt
        return ["task1", "task2", "task3"]

    def merge_results(self, results: List[Dict[str, str]]) -> List[Dict[str, str]]:
        # Placeholder for merging logic
        # This method should merge the results from multiple Coder instances
        merged_results = []
        for result in results:
            merged_results.extend(result)
        return merged_results

    def validate_code(self, project_path: str) -> bool:
        # Placeholder for validation logic
        # This method should validate the generated code
        return True

    async def generate_plan(self, prompt: str, repo_name: str, hash: str, timestamp: str, request: Request) -> str:
        s3_manager = S3Manager(hash, repo_name)
        coder_agent = CoderAgent(self.llm, repo_name)
        try:
            access_token = request.session.get("access_token")
            user = request.session.get("user")
            zip_contents = s3_manager.get_and_unzip_repo(timestamp)
            # Fetch repository structure and contents
            repository_structure = await get_repo_structure(repo_name, user['login'], access_token) # (zip_contents)
            logging.info(f"The repo structure is: \n{repository_structure}\n")
            repository_contents = await get_repo_code(zip_contents)
            logging.info(f"The repo contents are: \n{repository_contents}\n")

            # Use the fetched data in your agents
            planner_agent = PlannerAgent(self.llm)
            planner_agent.execute(prompt, repository_structure, repository_contents)
            
            logging.info("Step by step plan start \ns")
            step_by_step_plan = planner_agent.data["plan"]
            logging.info(f"The plan is: \n{step_by_step_plan}\n")

            return step_by_step_plan

        except HTTPException as http_ex:
            return {"status": "failed", "description": f"HTTP error: {http_ex.detail}"}
        except Exception as e:
            return {"status": "failed", "description": f"An error occurred: {str(e)}"}

    async def plan_orchestrator(self, prompt: str, repo_name: str, user_login: str, access_token: str) -> str:
        try:
            # Fetch repository structure and contents
            repository_structure = await get_repo_structure(repo_name, user_login, access_token)
            logging.info(f"The repo structure is: \n{repository_structure}\n")
            repository_contents = await get_repo_files_content(repo_name, user_login, access_token)
            logging.info(f"The repo contents are: \n{repository_contents}\n")

            # Use the fetched data in your agents
            planner_agent = PlannerAgent(self.llm)
            planner_agent.execute(prompt, repository_structure, repository_contents)
            
            logging.info("Step by step plan start \n")
            step_by_step_plan = planner_agent.data["plan"]
            logging.info(f"The plan is: \n{step_by_step_plan}\n")

            return step_by_step_plan

        except HTTPException as http_ex:
            return {"status": "failed", "description": f"HTTP error: {http_ex.detail}"}
        except Exception as e:
            return {"status": "failed", "description": f"An error occurred: {str(e)}"}
        

    async def generate_code(self, prompt: str, repo_name: str, hash: str, timestamp: str, step_by_step_plan) -> str:
        s3_manager = S3Manager(hash, repo_name)
        coder_agent = CoderAgent(self.llm, repo_name)
        try:
            json_plan = json.loads(step_by_step_plan)
            zip_contents = s3_manager.get_and_unzip_repo(timestamp)

            # Fetch repository structure and contents (filtered)
            repository_structure = await get_repo_structure(zip_contents)
            logging.info(f"The repo structure is: \n{repository_structure}\n")
            
            # Fetch filtered repository contents
            repository_contents = await get_repo_code(zip_contents)
            logging.info(f"The repo contents are: \n{repository_contents}\n")

            # Use the fetched data in your agents
            for step in step_by_step_plan:
                logging.info(f"\n At step {step} after coder")
                coder_agent.execute(step_by_step_plan=step_by_step_plan, curr_step=step, user_context=[], 
                                    repository_code=repository_contents, repository_structure=repository_structure)

            # Turn the repository_code dict back into a zip file, re-adding ignored files
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                # Add the filtered files to the zip
                for filename, content in repository_contents.items():
                    if content is not None:  # Skip files that failed to decode
                        # Write the file to the zip (re-encoding back to bytes)
                        zip_file.writestr(filename, content.encode('utf-8'))

                # Add back ignored files from the original zip_contents
                for filename, content in zip_contents.items():
                    if filename not in repository_contents:
                        # Add the ignored files back to the zip
                        zip_file.writestr(filename, content)
                
            # Seek to the start of the BytesIO buffer to prepare for reading
            zip_buffer.seek(0)

            # Upload the zip file back to S3
            s3_manager.upload_zip_file(zip_buffer.getvalue(), f"{repo_name}.zip")

            return {
                "status": "success",
                "description": "code generation completed",
                "timestamp": datetime.now().isoformat(),
                "zip_file": zip_buffer.getvalue()  # Optionally return the zip as bytes
            }

        except HTTPException as http_ex:
            return {"status": "failed", "description": f"HTTP error: {http_ex.detail}"}
        except Exception as e:
            return {"status": "failed", "description": f"An error occurred: {str(e)}"}



    async def execute_orchestrator(self, prompt: str, repo_name: str, user_login: str, access_token: str) -> str:
        try:
            # Fetch repository structure and contents
            repository_structure = await get_repo_structure(repo_name, user_login, access_token)
            logging.info(f"The repo structure is: \n{repository_structure}\n")
            repository_contents = await get_repo_files_content(repo_name, user_login, access_token)
            logging.info(f"The repo contents are: \n{repository_contents}\n")

            # Use the fetched data in your agents
            planner_agent = PlannerAgent(self.llm)
            planner_agent.execute(prompt, repository_structure, repository_contents)
            
            logging.info("Step by step plan start \n")
            step_by_step_plan = planner_agent.data["plan"]
            logging.info(f"The plan is: \n{step_by_step_plan}\n")

            logging.info("Coder agent start \n")
            coder = CoderAgent(self.llm, repo_name)
            for step in step_by_step_plan:
                logging.info(f"\n At step {step} after coder")
                coder.execute(step_by_step_plan=step_by_step_plan, curr_step=step, user_context=[], 
                              repository_code=repository_contents, repository_structure=repository_structure)

            logging.info("Executer agent start \n")

            return step_by_step_plan

        except HTTPException as http_ex:
            return {"status": "failed", "description": f"HTTP error: {http_ex.detail}"}
        except Exception as e:
            return {"status": "failed", "description": f"An error occurred: {str(e)}"}
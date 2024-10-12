import time
import json
import os
import subprocess
import re

from jinja2 import Environment, BaseLoader

from app.llm.llm import LLM
from app.agents.patcher.patcher import PatcherAgent

PROMPT = open(f"{os.getcwd()}/agents/executer/prompt.jinja2", "r").read().strip()
RERUNNER_PROMPT = open(f"{os.getcwd()}/agents/executer/rerun_prompt.jinja2", "r").read().strip()

class ExecuterAgent:
    def __init__(self, llm:LLM, user_prompt):
        self.llm = llm
        self.user_prompt = user_prompt

    def render(
        self,
        step_by_step_plan,
        repository_code,
        repository_structure,
        user_context,
        system_os: str
    ) -> str:
        env = Environment(loader=BaseLoader())
        template = env.from_string(PROMPT)
        return template.render(
            context=user_context,
            step_by_step_plan=step_by_step_plan,
            repository_code=repository_code,
            repository_structure=repository_structure,
            system_os=system_os,
        )

    def render_rerunner(
        self,
        step_by_step_plan,
        repository_code,
        repository_structure,
        user_context,
        system_os: str,
        commands: list,
        output: str,
        error: str
    ):
        env = Environment(loader=BaseLoader())
        template = env.from_string(RERUNNER_PROMPT)
        return template.render(
            context=user_context,
            step_by_step_plan=step_by_step_plan,
            repository_code=repository_code,
            repository_structure=repository_structure,
            system_os=system_os,
            commands=commands,
            output=output,
            error=error
        )

    def validate_rerunner_response(self, response: str):
        response = re.sub(r"```json|```", "", response).strip()
        if "action" not in response and "response" not in response:
            return False
        else:
            return response
        
    def validate_response(self, response):
        print(f"Raw response: {response}")

        if isinstance(response, str):
            # Remove markdown artifacts such as ```json and ```
            response = re.sub(r"```json|```", "", response).strip()
            
            try:
                response_dict = json.loads(response)
            except json.JSONDecodeError as e:
                print(f"JSON decode error: {e}")
                return False
        elif isinstance(response, dict):
            response_dict = response
        else:
            print("Response is neither a valid JSON string nor a dictionary.")
            return False

        print(f"Parsed response: {response_dict}")

        if "commands" not in response_dict:
            print("'commands' key not found in response.")
            return False
        else:
            return response_dict["commands"]



    def run_code(
            self,
            commands: list,
            project_path: str,
            project_name: str,
            step_by_step_plan,
            repository_code,
            repository_structure,
            user_context,
            system_os: str
        ):  
            retries = 0
            command_failed = False

            for command in commands:
                try:
                    process = subprocess.run(
                        command,
                        shell=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        cwd=project_path,
                        text=True
                    )
                    command_output = process.stdout
                    command_error = process.stderr
                    command_failed = process.returncode != 0

                    print("command_output %s", command_output)
                    print("command_error %s", command_error)

                    while command_failed and retries < 5:
                        prompt = self.render_rerunner(
                            step_by_step_plan,
                            repository_code,
                            repository_structure,
                            user_context,
                            system_os,
                            commands,
                            command_output,
                            command_error
                        )
                        response = self.llm.execute_query(prompt=prompt)
                        validated_response = self.validate_rerunner_response(response)
                        valid_response = json.loads(validated_response)
                        print(valid_response)

                        if not valid_response:
                            return {"status": "failed", "stdout": command_output, "stderr": command_error}

                        action = valid_response["action"]
                        
                        if action == "command":
                            command = valid_response["command"]
                            response = valid_response["response"]
                            
                            process = subprocess.run(
                                command,
                                shell=True,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                cwd=project_path,
                                text=True
                            )
                            command_output = process.stdout
                            command_error = process.stderr
                            command_failed = process.returncode != 0
                            
                            if command_failed:
                                retries += 1
                            else:
                                break
                        elif action == "patch":
                            response = valid_response["response"]
                            patcher_agent = PatcherAgent(project_dir=project_path, llm=self.llm)
                            response = patcher_agent.execute(user_prompt=self.user_prompt, repository_code=repository_code, 
                                                            repository_structure=repository_structure, user_context=user_context, output=command_output, error=command_error, commands=commands)

                            if response.get("status") == "success":
                                process = subprocess.run(
                                    command,
                                    shell=True,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE,
                                    cwd=project_path,
                                    text=True
                                )
                                command_output = process.stdout
                                command_error = process.stderr
                                command_failed = process.returncode != 0
                                
                                if command_failed:
                                    retries += 1
                                else:
                                    break
                            else:
                                return {"status": "failed", "stdout": command_output, "stderr": command_error}
                except Exception as e:
                    command_error = str(e)
                    command_failed = True
                    print("Exception: %s", command_error)
                
            if command_failed:
                return {"status": "failed", "stdout": command_output, "stderr": command_error}
                
            return {"status": "success", "stdout": command_output, "stderr": command_error}


    def execute(
        self,
        repository_code, 
        repository_structure,
        user_context,
        step_by_step_plan,
        os_system: str,
        project_path: str,
        project_name: str
    ) -> str:
        prompt = self.render(step_by_step_plan, repository_code, repository_structure, user_context, os_system)
        response = self.llm.execute_query(prompt=prompt).strip()
        print(response)
        valid_response = self.validate_response(response)
        print(valid_response)
        return self.run_code(
            valid_response,
            project_path,
            project_name,
            step_by_step_plan,
            repository_code,
            repository_structure,
            user_context,
            os_system
        )

        # return valid_response
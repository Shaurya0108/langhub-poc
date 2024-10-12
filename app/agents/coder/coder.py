import logging
import os
from typing import List, Dict, Union
from jinja2 import Environment, BaseLoader
from app.llm.llm import LLM

class CoderAgent:
    def __init__(self, llm: LLM, project_dir: str, prompt_path: str = None):
        self.project_dir = project_dir
        self.llm = llm
        self.prompt_path = prompt_path or f"{os.getcwd()}/agents/coder/prompt.jinja2"
        self.env = Environment(loader=BaseLoader())
        self.prompt_template = self._load_prompt(self.prompt_path)

    def _load_prompt(self, prompt_path) -> str:
        try:
            with open(prompt_path) as file:
                return file.read().strip()
        except FileNotFoundError:
            raise ValueError(f"Prompt file not found at {prompt_path}")

    def _generate_prompt(self, step_by_step_plan: str, curr_step: str, repository_code: Dict[str, str], repository_structure: Dict[str, Union[str, List]], user_context: List[str]) -> str:
        template = self.env.from_string(self.prompt_template)
        return template.render(
            step_by_step_plan=step_by_step_plan,
            curr_step=curr_step,
            user_context=user_context,
            repository_code=repository_code,
            repository_structure=repository_structure['contents'] if 'contents' in repository_structure else []
        )

    def _get_llm_response(self, prompt: str) -> str:
        return self.llm.execute_query(prompt)

    def _validate_response_format(self, response: str) -> bool:
        # Check if response is in the expected markdown format
        if response.startswith("~~~") and response.endswith("~~~") and "File:" in response:
            return True
        template = self.env.from_string(self._load_prompt(f"{os.getcwd()}/agents/coder/recode_prompt.jinja2"))
        recode_prompt = template.render(
            previous_response = response
        )
        return self._validate_response_format(self._get_llm_response(recode_prompt))

    def _reformat_response(self, response: str) -> str:
        # If the response is not correctly formatted, request the LLM to reformat
        reformatted_prompt = f"Please reformat the following response to the correct format:\n\n{response}"
        return self._get_llm_response(reformatted_prompt)

    def _save_code_to_project(self, response: List[Dict[str, str]], repository_code: Dict[str, str], repository_structure: List[str]):
        logging.info(f"Saving code to project. Response: {response}")
        logging.info(f"Current repository_structure: {repository_structure}")
        for file in response:
            file_name = file['file']
            file_content = file['code']
            
            logging.info(f"Processing file: {file_name}")
            
            # Update repository_code
            repository_code[file_name] = file_content
            
            # Update repository_structure
            if file_name not in repository_structure:
                logging.info(f"Adding {file_name} to repository_structure")
                repository_structure.append(file_name)
            
            # Save to actual file system
            file_path = os.path.join(self.project_dir, file_name)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(file_content)
        
        logging.info(f"Updated repository_structure: {repository_structure}")

    def execute(self, step_by_step_plan: str, curr_step: str, user_context: List[str], repository_code: Dict[str, str], repository_structure: List[str]) -> Union[List[Dict[str, str]], bool]:
        try:
            logging.info(f"Starting execute method")
            logging.info(f"repository_code type: {type(repository_code)}")
            logging.info(f"repository_structure type: {type(repository_structure)}")
            
            prompt = self._generate_prompt(step_by_step_plan, curr_step, repository_code, repository_structure, user_context)
            logging.info(f"The prompt inside the coder is \n{prompt}")

            response = self._get_llm_response(prompt)
            logging.info(f"The response inside the coder is \n{response}")

            if not self._validate_response_format(response):
                response = self._reformat_response(response)

            valid_response = self._parse_valid_response(response)
            logging.info(f"The validated response inside the coder is \n{valid_response}")

            if not valid_response:
                return False

            self._save_code_to_project(valid_response, repository_code, repository_structure)
            return valid_response
        except Exception as e:
            logging.error(f"An error occurred in execute: {str(e)}", exc_info=True)
            return False

    def _parse_valid_response(self, response: str) -> List[Dict[str, str]]:
        # Parsing the response to extract code blocks in the specified format
        response = response.strip().strip("~~~")
        files = []
        current_file = None
        current_code = []

        for line in response.splitlines():
            if line.startswith("File:"):
                if current_file:
                    files.append({"file": current_file, "code": "\n".join(current_code)})
                current_file = line.split(":")[1].strip()
                current_code = []
            elif line.startswith("```"):
                continue
            else:
                current_code.append(line)

        if current_file:
            files.append({"file": current_file, "code": "\n".join(current_code)})
        
        return files

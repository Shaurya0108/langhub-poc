import logging
from jinja2 import Environment, BaseLoader
import os
import json
from app.llm.llm import LLM
from app.agents.processor.processor import Processor

class PlannerAgent:
    def __init__(self, llm: LLM, index_name="repo-index"):
        # self.repo_path = repo_path
        self.llm = llm
        # self.processor = processor
        self.index_name = index_name
        self.data = self._initialize_data()
        self.env = Environment(loader=BaseLoader())

    def _initialize_data(self):
        return {
            "current_focus": "",
            "plan": []
        }

    def _load_prompt(self, path):
        try:
            with open(path) as file:
                return file.read().strip()
        except FileNotFoundError:
            raise ValueError(f"Prompt file not found at {path}")

    def execute(self, user_prompt, repository_structure, repository_code, prompt_path=None):
        try:
            prompt_template = self._load_prompt(prompt_path or f"{os.getcwd()}/agents/planner/prompt.jinja2")
            logging.info(f"The initial prompt in planner is: \n{user_prompt}\n")
            prompt = self._generate_prompt(prompt_template, repository_structure, repository_code, user_prompt)
            logging.info(f"The final prompt in planner is: \n{prompt}\n")
            response = self._get_llm_response(prompt)
            logging.info(f"The llm response in planner is: \n{response}\n")
            self._parse_response(response)
            return self.data.get('plan')
        except Exception as e:
            return {"status": "failed", "description": f"An error occurred in planner exec: {str(e)}"} 

    def execute_rerun(self, user_prompt, output, error, commands, rerun_prompt_path=None):
        repository_structure = self._get_repository_structure()
        repository_code = self._get_relevant_code(user_prompt)

        rerun_prompt_template = self._load_prompt(rerun_prompt_path or f"{os.getcwd()}/agents/planner/rerun_prompt.jinja2")
        prompt = self._generate_prompt(rerun_prompt_template, repository_structure, repository_code, user_prompt, output, error, commands)
        response = self._get_llm_response(prompt)
        self._parse_response(response)
    
    def _generate_prompt(self, template_str, repository_structure, repository_code, user_prompt, output=None, error=None, commands=None):
        if not template_str:
            raise ValueError("Prompt template is empty.")
        
        template = self.env.from_string(template_str)
        return template.render(
            prompt=user_prompt,
            repository_code=repository_code,
            repository_structure=repository_structure,
            output=output,
            error=error,
            commands=commands
        )

    def _get_llm_response(self, prompt):
        return self.llm.execute_query(prompt)

    def _parse_response(self, response):
        try:
            lines = response.split("\n")
            current_section = None
            current_step = {}
            steps = []

            for line in lines:
                line = line.strip()

                if line.startswith("Current Focus:"):
                    self.data["current_focus"] = line.split("Current Focus:")[1].strip()
                    current_section = "current_focus"

                elif line.startswith("Plan:"):
                    current_section = "plan"

                elif current_section == "plan":
                    if line.startswith("- Step"):
                        if current_step:
                            steps.append(current_step)
                        step_number = line.split(":")[0].strip().split(" ")[2]
                        current_step = {
                            "step": step_number,
                            "file": "",
                            "action": "",
                            "description": ""
                        }
                    elif line.startswith("- File:"):
                        current_step["file"] = line.split(": ")[1].strip()
                    elif line.startswith("- Action:"):
                        current_step["action"] = line.split(": ")[1].strip()
                    elif line.startswith("- Description:"):
                        current_step["description"] = line.split(": ")[1].strip()
                    elif line and current_step["description"]:
                        current_step["description"] += " " + line.strip()

            if current_step:
                steps.append(current_step)

            # Remove triple backticks from the last step's description
            if steps:
                steps[-1]["description"] = steps[-1]["description"].replace("```", "")

            self.data["plan"] = steps
            logging.info("Added plan to data")
        except Exception as e:
            logging.info("Plan add to data failed")
            return {"status": "failed", "description": f"An error occurred in planner parse response: {str(e)}"}
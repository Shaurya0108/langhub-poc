import os

from jinja2 import Environment, BaseLoader
from typing import List, Dict, Union
from app.agents.planner.planner import PlannerAgent
from app.agents.coder.coder import CoderAgent
from app.llm.llm import LLM

PROMPT = open(f"{os.getcwd()}/agents/patcher/prompt.jinja2", "r").read().strip()

class PatcherAgent:
    def __init__(self, project_dir, llm):
        self.project_dir = project_dir
        
        self.llm = llm

    def render(
        self,
        conversation: list,
        code_markdown: str,
        commands: list,
        error :str,
        system_os: str
    ) -> str:
        env = Environment(loader=BaseLoader())
        template = env.from_string(PROMPT)
        return template.render(
            conversation=conversation,
            code_markdown=code_markdown,
            commands=commands,
            error=error,
            system_os=system_os
        )

    def validate_response(self, response: str) -> Union[List[Dict[str, str]], bool]:
        response = response.strip()

        response = response.split("~~~", 1)[1]
        response = response[:response.rfind("~~~")]
        response = response.strip()

        result = []
        current_file = None
        current_code = []
        code_block = False

        for line in response.split("\n"):
            if line.startswith("File: "):
                if current_file and current_code:
                    result.append({"file": current_file, "code": "\n".join(current_code)})
                current_file = line.split("`")[1].strip()
                current_code = []
                code_block = False
            elif line.startswith("```"):
                code_block = not code_block
            else:
                current_code.append(line)

        if current_file and current_code:
            result.append({"file": current_file, "code": "\n".join(current_code)})

        return result

    def save_code_to_project(self, response: List[Dict[str, str]], project_name: str):
        file_path_dir = None
        project_name = project_name.lower().replace(" ", "-")

        for file in response:
            file_path = os.path.join(self.project_dir, project_name, file['file'])
            file_path_dir = os.path.dirname(file_path)
            os.makedirs(file_path_dir, exist_ok=True)
    
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(file["code"])
    
        return file_path_dir
    def get_project_path(self, project_name: str):
        project_name = project_name.lower().replace(" ", "-")
        return f"{self.project_dir}/{project_name}"

    def response_to_markdown_prompt(self, response: List[Dict[str, str]]) -> str:
        response = "\n".join([f"File: `{file['file']}`:\n```\n{file['code']}\n```" for file in response])
        return f"~~~\n{response}\n~~~"

    def execute(
        self,
        user_prompt,
        repository_code,
        repository_structure,
        user_context,
        output,
        error,
        commands
    ) -> str:
        # generate plan by passing in error and context
        planner_agent = PlannerAgent(self.project_dir, self.llm)
        planner_agent.execute_rerun(repository_structure=repository_structure, repository_code=repository_code, user_prompt=user_prompt, output=output, error=error, commands=commands)
        # code the plan
        for step in planner_agent.plan:
            coder = CoderAgent(self.llm, self.project_dir)
            coder.execute(planner_agent.plan, step, user_context, repository_code, repository_structure)
        # return so that the runner and retry running it
        return {"status": "success", "description": "completed patching"}
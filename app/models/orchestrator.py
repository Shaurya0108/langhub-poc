from pydantic import BaseModel

class OrchestratorRequest(BaseModel):
    provider: str
    model: str
    api_key: str
    api_base_url: str = None
    prompt: str
    repo_url: str

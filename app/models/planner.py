from pydantic import BaseModel, Field

class GeneratePlanRequest(BaseModel):
    prompt: str
    repo_name: str
    hash: str
    timestamp: str
    provider: str = "openai"
    model: str = "gpt-3.5-turbo"

class StorePlanRequest(BaseModel):
    repo_name: str
    hash: str
    plan: str = Field(..., min_length=1)
from app.llm.cluade.claude_client import ClaudeClient
from app.llm.openai.openai_client import OpenAIClient
class LLM:
    def __init__(self, provider: str, model: str, api_key: str, api_base_url: str = None):
        self.provider = provider
        self.model = self._initialize_model(provider, model, api_key, api_base_url)

    def _initialize_model(self, provider: str, model: str, api_key: str, api_base_url: str = None):
        if provider.lower() == 'openai':
            return OpenAIClient(model, api_key)
        elif provider.lower() == 'claude':
            return ClaudeClient(model, api_key, api_base_url)
        else:
            raise ValueError(f"Unsupported provider: {provider}")

    def execute_query(self, prompt: str) -> str:
        return self.model.execute_query(prompt)
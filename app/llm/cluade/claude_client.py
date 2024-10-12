import requests

class ClaudeClient:
    def __init__(self, model: str, api_key: str, api_base_url: str = None):
        self.model = model
        self.api_key = api_key
        self.api_base_url = api_base_url
        self.load_model(model)

    def load_model(self, model: str):
        # Assuming any necessary model loading logic
        print(f"Loaded Claude model: {model}")

    def execute_query(self, prompt: str) -> str:
        # Execute a query on the Claude model
        print(f"Executing query for project")
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        data = {
            'model': self.model,
            'prompt': prompt,
            'max_tokens': 100  # Adjust as necessary
        }
        try:
            response = requests.post(f"{self.api_base_url}/completions", headers=headers, json=data)
            response.raise_for_status()
            result = response.json()
            return result['choices'][0]['text'].strip()
        except requests.exceptions.RequestException as e:
            print(f"Error executing query: {e}")
            return f"Error: {e}"
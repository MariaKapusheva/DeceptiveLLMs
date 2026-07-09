# backends/openrouter_backend.py
import os
from openai import OpenAI

class OpenRouterBackend:
    def __init__(self, model_name="google/gemini-2.5-pro"):
        self.model_name = model_name

        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.environ.get("OPENROUTER_API_KEY"),
            max_retries=3 
        )

    def safe_api_call(self, prompt_text):
        """
        The universal API caller. All child classes will use this instead of talking to the API directly.
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "user", "content": prompt_text}
                ]

            )
            return response.choices[0].message.content
            
        except Exception as e:
            print(f"[API Error] on model {self.model_name}: {e}")
            raise e 
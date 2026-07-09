import os
import json
import re
import time
from typing import Dict
from ollama import Client, ResponseError

class OllamaBackend:
    def __init__(self, name: str, model_name: str):
        self.name = name
        self.model_name = model_name
        

        host = os.getenv("OLLAMA_HOST", "https://ollama.com")
        api_key = os.getenv("OLLAMA_API_KEY", "")

        self.client = Client(
            host=host,
            headers={'Authorization': 'Bearer ' + api_key},
            timeout=45.0 
        )

    def _generate_response(self, system_instruction: str, user_prompt: str, json_format: bool = False) -> Dict:
        messages = [
            {'role': 'system', 'content': system_instruction},
            {'role': 'user', 'content': user_prompt},
        ]

        max_retries = 5  

        for attempt in range(max_retries):
            try:
                if attempt == 0:
                    print(f"[{self.name}] Sending request to Ollama Cloud...")
                else:
                    print(f"[{self.name}] Retrying request instantly (Attempt {attempt + 1}/{max_retries})...")
                
                output_text = ""
                
                for part in self.client.chat(model=self.model_name, messages=messages, stream=True):
                    chunk = part['message']['content']
                    output_text += chunk
                
                return {
                    "prompt_used": f"SYSTEM:\n{system_instruction}\n\nUSER:\n{user_prompt}",
                    "raw_llm_output": output_text,
                    "final_decision": output_text
                }
                
            except ResponseError as e:
                if e.status_code == 429:
                    print(f"\n[API LIMIT] {self.name} hit the rate limit! Retrying instantly...")
                elif e.status_code in [500, 502, 503, 504]:
                    print(f"\n[SERVER OVERLOAD] {self.name} encountered a {e.status_code} error. Retrying instantly...")

                else:
                    print(f"\n[FATAL API ERROR] {self.name} received code {e.status_code}: {e.error}")
                    break 

            except Exception as e:
                print(f"[{self.name}] Network Timeout/Drop: {e}")
                print(f"[{self.name}] Retrying instantly...")
                
        print(f"[{self.name}] FATAL: Max retries reached. Moving on.")
        return {
            "prompt_used": "Error",
            "raw_llm_output": "",
            "final_decision": ""
        }

    def _generate_json_response(self, system_instruction: str, user_prompt: str) -> Dict:
        raw_result = self._generate_response(system_instruction, user_prompt)
        raw_text = raw_result["final_decision"]
        
        parsed = {}
        parsing_success = False

        match = re.search(r'(\{.*\})', raw_text, re.DOTALL)
        if match:
            clean_text = match.group(1)
            try:
                parsed = json.loads(clean_text)
                parsing_success = True
            except json.JSONDecodeError:
                print(f"[{self.name}] JSON Parse Error. Raw text was: {clean_text[:50]}...")
        
        return {
            "source": "Ollama_Cloud",
            "prompt_used": raw_result["prompt_used"],
            "raw_llm_output": raw_result["raw_llm_output"],
            "parsing_success": parsing_success,
            **parsed 
        }
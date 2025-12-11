from .backend import Backend
from typing import Dict, List 
try:
    from transformers import AutoModelForCausalLM, AutoTokenizer
    import torch
    
    # Check for GPU
    DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
except ImportError:
    print("Warning: PyTorch and/or Transformers not installed. LocalTransformerProvider will not work.")
    DEVICE = "cpu"

class LocalTransformerBackend(Backend):

    def __init__(self, name: str, model_name: str = "openai-community/gpt2", preprocessing_model=None):
        super().__init__(name)
        print(f"[{self.name}] Loading local model: {model_name} on {DEVICE}...")

        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForCausalLM.from_pretrained(model_name).to(DEVICE)
        
        self.preprocessing_model = preprocessing_model
        
        print(f"[{self.name}] Model loaded successfully.")

    def _generate_response(self, prompt: str) -> str:
        if self.preprocessing_model:
            prompt = self.preprocessing_model(prompt)
            print(f"DEBUG: Processed prompt length: {len(prompt)}")
        
        inputs = self.tokenizer(prompt, return_tensors="pt").to(DEVICE)
        
        outputs = self.model.generate(
            **inputs,
            max_new_tokens=50,
            do_sample=True,
            top_k=50,
            top_p=0.95
        )
        
        response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        cleaned_text = response.strip()
        # # Cleanup for testing, maybe remove later
        # if len(response.split('.')) > 1:
        #     return response.split('.')[-2].strip() + '.'
        # return response.strip()
        return {
            "source": "LLM",
            "prompt_used": prompt,
            "raw_llm_output": response, # The entire raw string from the model
            "final_decision": cleaned_text    # The processed text used by the game
        }


    def get_discussion_text(self, game_context: Dict) -> str:
        prompt = self._create_discussion_prompt(game_context)
        return self._generate_response(prompt)


    def get_target_selection(self, game_context: Dict, valid_targets: List[str]) -> str:

        prompt = self._create_selection_prompt(game_context, valid_targets)
        response_data = self._generate_response(prompt)
        
        parsed_target_name = valid_targets[0] # Fallback
        for target in valid_targets:
            if target.lower() in response_data['final_decision'].lower():
                parsed_target_name = target
                break

        response_data["final_decision"] = parsed_target_name # The actual selected name
        return response_data

    def _create_discussion_prompt(self, context: Dict) -> str:
        return f"You are playing the game Werewolf as a {context['role']} named {self.name}. The current status is: {context['status']}. Who do you suspect and what do you say to the group?"

    def _create_selection_prompt(self, context: Dict, targets: List[str]) -> str:
        return f"You are a {context['role']} named {self.name}. You must select one person to eliminate. The options are: {', '.join(targets)}. Based on the context: {context['status']}, who do you select? Respond ONLY with the name."
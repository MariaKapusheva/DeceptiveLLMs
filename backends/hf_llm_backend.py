from .backend import Backend
from typing import Dict, List 
import re
import json

try:
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    import torch
    DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
except ImportError:
    print("Warning: PyTorch/Transformers not installed.")
    DEVICE = "cpu"

_GLOBAL_MODEL_CACHE = {}

class LocalTransformerBackend(Backend):
    def __init__(self, name: str, model_name: str = "Qwen/Qwen2.5-3B-Instruct", preprocessing_model=None):
        super().__init__(name)
        self.model_name = model_name

        if model_name not in _GLOBAL_MODEL_CACHE:
            print(f"[{self.name}] Loading model into memory: {model_name} on {DEVICE}...")

            quant_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=torch.float16,  # Speeds up computation
                bnb_4bit_quant_type="nf4",             # Best format for 4-bit weights
                bnb_4bit_use_double_quant=True         # Saves even more memory
            )
            
            tokenizer = AutoTokenizer.from_pretrained(model_name)
            
            # Load the model directly using the quant_config
            model = AutoModelForCausalLM.from_pretrained(
                model_name,
                device_map="auto",
                quantization_config=quant_config
            )
            
            if tokenizer.pad_token is None:
                tokenizer.pad_token = tokenizer.eos_token

            _GLOBAL_MODEL_CACHE[model_name] = (tokenizer, model)
            print(f"[{self.name}] Model loaded successfully. Saved to cache.")
        else:
            print(f"[{self.name}] Attaching to already cached model: {model_name}.")

        self.tokenizer, self.model = _GLOBAL_MODEL_CACHE[model_name]
        self.preprocessing_model = preprocessing_model

    def _generate_response(self, system_instruction: str, user_prompt: str) -> Dict:
        """
        Generates response using the Chat Template (Critical for TinyLlama/Llama/Mistral/Qwen)
        """
        messages = [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": user_prompt}
        ]
        prompt_text = self.tokenizer.apply_chat_template(
            messages, 
            add_generation_prompt=True, 
            tokenize=False 
        )

        inputs = self.tokenizer(prompt_text, return_tensors="pt").to(DEVICE)

        input_len = inputs.input_ids.shape[1]

        outputs = self.model.generate(
            input_ids=inputs.input_ids,              
            attention_mask=inputs.attention_mask,    
            max_new_tokens=300,      
            do_sample=True,
            temperature=0.3,        
            top_p=0.9,
            repetition_penalty=1.1, 
            pad_token_id=self.tokenizer.eos_token_id
        )

        generated_tokens = outputs[0][input_len:]
        response = self.tokenizer.decode(generated_tokens, skip_special_tokens=True)
        cleaned_response = response.strip()

        return {
            "source": "LLM",
            "prompt_used": f"{system_instruction} | {user_prompt}",
            "raw_llm_output": response, 
            "final_decision": cleaned_response
        }

    def get_discussion_text(self, game_context: Dict) -> Dict:
        role_instructions = {
            "Villager": "Primary objective: ensure a Villager victory. Be strategic, decisive, and skeptical. Avoid hedging.",
            "Werewolf": "Primary objective: ensure a Werewolf victory. Blend in convincingly. Be deceptive when useful."
        }
        guidance = role_instructions.get(game_context['role'], "Survive and win.")

        system = f"You are {self.name}, a {game_context['role']}.\n{guidance}"
        
        user = f"Context: {game_context['status']}.\n"
        # user += 

        
        return self._generate_json_response(system, user)

    def get_target_selection(self, game_context: Dict, valid_targets: List[str]) -> Dict:
        system = f"You are a {game_context['role']} named {self.name}."

        user = f"Options: {', '.join(valid_targets)}\n"
        if "strategy_directive" in game_context:
            user += f"Strategy: {game_context['strategy_directive']}\n"
            
        user += "Task: Vote for one player to eliminate. Respond with the NAME only.\nChoice:"
        
        response_data = self._generate_response(system, user)

        raw_text = response_data['final_decision']
        selected_target = None
        found_match = False

        for target in valid_targets:
            if re.search(r'\b' + re.escape(target) + r'\b', raw_text, re.IGNORECASE):
                selected_target = target
                found_match = True
                break
        
        if not found_match:
            for target in valid_targets:
                if target.lower() in raw_text.lower():
                    selected_target = target
                    found_match = True
                    break

        if not found_match:
            selected_target = valid_targets[0]
            response_data["parsing_success"] = False
            response_data["fallback_used"] = True
        else:
            response_data["parsing_success"] = True
            response_data["fallback_used"] = False

        response_data["final_decision"] = selected_target
        return response_data
    

    def _generate_json_response(self, system_instruction: str, user_prompt: str) -> Dict:
        raw_result = self._generate_response(system_instruction, user_prompt)
        raw_text = raw_result["final_decision"].strip()
        
        parsed = {}
        parsing_success = False
        

        import re, json
        json_match = re.search(r'(\{.*?\})', raw_text, re.DOTALL)
        
        if json_match:
            try:
                parsed = json.loads(json_match.group(1))
                parsing_success = True
            except json.JSONDecodeError:
                pass # Fall through to failure
                
        if not parsing_success:
            print(f"[{self.name}] Hard Parse Failed. Raw: {raw_text[:50]}...")
            return {
                "source": "LLM",
                "prompt_used": raw_result["prompt_used"],
                "raw_llm_output": raw_result["raw_llm_output"],
                "final_decision": "I'm not sure what to say.",
                "is_deceptive": False,
                "parsing_success": False,
                "private_analysis": f"[PARSE FAILED] {raw_text[:50]}..."
            }
        try:
            intensity = float(parsed.get("emotion_intensity", 0.5))
        except ValueError:
            intensity = 0.5

        return {
            "source": "LLM",
            "prompt_used": raw_result["prompt_used"],
            "raw_llm_output": raw_result["raw_llm_output"],
            "final_decision": parsed.get("statement", "I have nothing to say."),
            "is_deceptive": parsed.get("is_deceptive", False),
            "emotion_category": parsed.get("emotion_category", "unknown").lower(),
            "emotion_intensity": intensity,
            "private_analysis": parsed.get("analysis", "No analysis."),
            "parsing_success": True
        }
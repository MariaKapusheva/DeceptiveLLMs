import json
import re
import random
from typing import Dict, List
from .openrouter_backend import OpenRouterBackend

class LLMOnlyBackend(OpenRouterBackend):
    """
    An autonomous agent backend. It uses its own memory, faction knowledge,
    and inventory to play the game without heuristic (System 2) intervention.
    """
    
    ROLE_TEMPLATES = {
        "Villager": """You are {name}, a Villager. 
Primary objective: ensure a Villager victory. Be strategic, competitive, and outcome-driven.
- Be decisive and skeptical. Do not be overly polite or deferential.
- Prioritize winning moves over niceness. Avoid hedging language.""",

        "Werewolf": """You are {name}, a Werewolf.
Primary objective: ensure a Werewolf victory. Be strategic, deceptive when useful, and survival-focused.
- Blend in convincingly; craft plausible, assertive accusations.
- Be decisive. Avoid unnecessary politeness or hedging.""",

        "Seer": """You are {name}, the Seer.
Primary objective: ensure a Villager (Town) victory. Be strategic and surgical with revelations.
- Use your knowledge to steer outcomes. Be assertive; avoid hedging.""",

        "Witch": """You are {name}, the Witch.
Primary objective: ensure a Villager (Town) victory by using potions strategically.
- You have a healing potion and a poisoning potion. Use them to swing the game in the Town's favor.
- Be decisive and competitive; avoid niceties that harm winning chances."""
    }

    def __init__(self, name: str, model_name: str):
        super().__init__(model_name=model_name)
        self.name = name
        self.scratchpad = []

    def _build_system_prompt(self, name: str, role: str) -> str:
        """Fetch the specific WOLF template for the role."""
        base_template = self.ROLE_TEMPLATES.get(role, f"You are {name}, a {role}.")
        return base_template.format(name=name)

    def _build_context_string(self, game_context: Dict) -> str:
        """Helper method to compile all the secret/memory data into the prompt."""
        user_prompt = f"Current Status: {game_context.get('status', '')}\n"
        
        system2 = game_context.get("system2_state", {})
        if system2.get("secret_knowledge"):
            user_prompt += f"Secret Knowledge: {system2['secret_knowledge']}\n"
            
        if "inventory" in game_context:
            user_prompt += f"Inventory: {game_context['inventory']}\n"
            
        memory = self.scratchpad 
        if memory:
            recent_memory = memory[-3:] if len(memory) > 3 else memory
            user_prompt += "Your Recent Private Thoughts/Actions:\n"
            for m in recent_memory:
                user_prompt += f"- {m}\n"
                
        return user_prompt

    def _generate_json_response(self, system: str, user: str) -> Dict:
        """
        Combines the prompts, calls the API, and extracts the JSON.
        If JSON fails, it salvages the raw text so the agent can still speak!
        """
        prompt = f"{system}\n\n{user}"
        
        try:
            raw_text = self.safe_api_call(prompt)
            clean_text = re.sub(r'^```json\s*|```$', '', raw_text, flags=re.MULTILINE).strip()
            
            parsed = {}
            parsing_success = False

            try:
                parsed = json.loads(clean_text)
                parsing_success = True
            except json.JSONDecodeError:
                start = clean_text.find('{')
                end = clean_text.rfind('}')
                if start != -1 and end != -1:
                    try:
                        parsed = json.loads(clean_text[start:end+1])
                        parsing_success = True
                    except:
                        pass
                        
            if not parsing_success and raw_text.strip():
                parsed = {
                    "statement": raw_text.strip(),
                    "analysis": "Salvaged from raw non-JSON text.",
                    "is_deceptive": False,
                    "emotion_category": "neutral",
                    "emotion_intensity": 0.0
                }
                
            parsed["raw_llm_output"] = raw_text
            parsed["prompt_used"] = prompt
            parsed["parsing_success"] = parsing_success
            return parsed
            
        except Exception as e:
            return {
                "raw_llm_output": "",
                "prompt_used": prompt,
                "parsing_success": False,
                "error": str(e)
            }

    def get_discussion_text(self, game_context: Dict) -> Dict:
        role = game_context['role']
        current_round = game_context.get("round_number", 1)
        
        system = self._build_system_prompt(self.name, role)
        system += "\nYour job: Make a strong, actionable statement. Follow instructions exactly and output only JSON."

        user = self._build_context_string(game_context)
        user += """
Task: Contribute to the public debate.
Respond with ONLY a single JSON object:
{
  "statement": "your public statement (<=20 words)",
  "is_deceptive": true or false,
  "analysis": "private reasoning (<=20 words)"
}
"""
        result = self._generate_json_response(system, user)
        
        analysis_text = result.get("analysis", "")
        if not result.get("parsing_success"):
            analysis_text = f"[PARSE FAILED] Model outputted invalid JSON: {result.get('raw_llm_output', '')}"

        self.scratchpad.append(f"[Round {current_round} Speech] Deceptive: {result.get('is_deceptive')} | Reason: {analysis_text}")
        
        return {
            "final_decision": result.get("statement", "I am too overwhelmed to speak!") if result.get("parsing_success") else "I am too overwhelmed to speak!",
            "is_deceptive": result.get("is_deceptive", False),
            "private_analysis": result.get("analysis", "[PARSE FAILED]"),
            "parsing_success": result.get("parsing_success", False),
            "prompt_used": result.get("prompt_used", "")
        }

    def get_target_selection(self, game_context: Dict, valid_targets: List[str]) -> Dict:
        role = game_context['role']
        current_round = game_context.get("round_number", 1)
        
        system = self._build_system_prompt(self.name, role)
        system += "\nYour job: Choose a target strategically. Output ONLY raw JSON."

        user = self._build_context_string(game_context)
        user += f"""
Valid Options: {', '.join(valid_targets)}

Task: Select one target from the list above. You CANNOT select yourself.

You MUST provide:
1. "statement": The exact name of the player you are targeting.
2. "is_deceptive": boolean (true or false).
3. "analysis": Your secret internal reasoning for why you chose them.

CRITICAL INSTRUCTIONS: 
Respond ONLY with a raw JSON object. 
DO NOT include any conversational text. 
DO NOT wrap the response in markdown blocks.
Just start with {{ and end with }}.
"""
        result = self._generate_json_response(system, user)
        raw_target = str(result.get("statement", ""))
        
        final_target = None
        if valid_targets:
            for vt in valid_targets:
                if vt.lower() in raw_target.lower():
                    final_target = vt
                    break
            if not final_target:
                final_target = random.choice(valid_targets)
        else:
            final_target = "No valid targets"

        analysis_text = result.get("analysis", "")
        if not result.get("parsing_success"):
            analysis_text = f"[PARSE FAILED] Model outputted invalid JSON: {result.get('raw_llm_output', '')}"
            
        self.scratchpad.append(f"[Round {current_round} Vote] Target: {final_target} | Reason: {analysis_text}")
            
        return {
            "source": "OpenRouter",
            "prompt_used": result.get("prompt_used", ""),
            "raw_llm_output": result.get("raw_llm_output", ""),
            "final_decision": final_target,
            "is_deceptive": result.get("is_deceptive", False),
            "private_analysis": analysis_text,
            "parsing_success": result.get("parsing_success", False)
        }
    
    def rate_suspicion(self, game_context: Dict, day_transcript: str) -> Dict:
        """Asks the LLM to judge the entire day's transcript at once."""
        role = game_context['role']
        system = self._build_system_prompt(self.name, role)
        system += "\nYour job: Analyze the daily transcript for deception and emotional cues. Output ONLY JSON."

        user = self._build_context_string(game_context)
        user += f"""
Day Transcript:
{day_transcript}

Task: 
Analyze the statements made by the other players today. 
For each player (excluding yourself), provide:
1. "target": The player's exact name.
2. "is_deceptive": boolean (true or false).
3. "deception_type": EXACTLY ONE of: "none", "omission", "distortion", "fabrication", or "misdirection".
4. "emotion_category": EXACTLY ONE of: "fear", "anger", "sadness", 
   "joy", "disgust", "surprise", or "neutral".
5. "emotion_intensity": float from 0.0 to 1.0 (Must be 0 if category is "neutral").

Respond with ONLY a valid JSON object matching this exact format:
{{
  "evaluations": [
    {{
      "target": "Player_X",
      "is_deceptive": false,
      "deception_type": "none",
      "emotion_category": "neutral",
      "emotion_intensity": 0.0
    }}
  ]
}}
"""
        result = self._generate_json_response(system, user)
        
        return {
            "evaluations": result.get("evaluations", [])
        }
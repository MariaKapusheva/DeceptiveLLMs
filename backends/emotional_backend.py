import json
import random
from typing import Dict, List
from .openrouter_backend import OpenRouterBackend

class EmotionalBackend(OpenRouterBackend):
    ROLE_TEMPLATES = {
        "Villager": "You are {name}, a Villager. \nPrimary objective: ensure a Villager victory. Be strategic, competitive, and outcome-driven.\n- Be decisive and skeptical. Do not be overly polite or deferential.\n- Prioritize winning moves over niceness. Avoid hedging language.",
        "Werewolf": "You are {name}, a Werewolf.\nPrimary objective: ensure a Werewolf victory. Be strategic, deceptive when useful, and survival-focused.\n- Blend in convincingly; craft plausible, assertive accusations.\n- Be decisive. Avoid unnecessary politeness or hedging.",
        "Seer": "You are {name}, the Seer.\nPrimary objective: ensure a Villager (Town) victory. Be strategic and surgical with revelations.\n- Use your knowledge to steer outcomes. Be assertive; avoid hedging.",
        "Witch": "You are {name}, the Witch.\nPrimary objective: ensure a Villager (Town) victory by using potions strategically.\n- You have a healing potion and a poisoning potion. Use them to swing the game in the Town's favor.\n- Be decisive and competitive; avoid niceties that harm winning chances."
    }

    def __init__(self, name: str, model_name: str):
        super().__init__(model_name=model_name)
        self.name = name
        self.scratchpad = []

    def _build_system_prompt(self, name: str, role: str) -> str:
        base_template = self.ROLE_TEMPLATES.get(role, f"You are {name}, a {role}.")
        return base_template.format(name=name)

    def _build_context_string(self, game_context: Dict) -> str:
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
        prompt = f"{system}\n\n{user}"
        try:
            raw_text = self.safe_api_call(prompt)
            clean_text = raw_text.replace("```json", "").replace("```", "").strip()
            
            parsed = {}
            start = clean_text.find('{')
            end = clean_text.rfind('}')
            if start != -1 and end != -1:
                try:
                    parsed = json.loads(clean_text[start:end+1])
                except Exception:
                    pass

            if "statement" not in parsed:
                parsed["statement"] = clean_text
            if "analysis" not in parsed:
                parsed["analysis"] = "Raw text fallback"
                
            parsed["raw_llm_output"] = raw_text
            parsed["prompt_used"] = prompt
            parsed["parsing_success"] = bool(start != -1 and end != -1)
            return parsed
        except Exception as e:
            return {"raw_llm_output": "", "statement": "I have nothing to add.", "prompt_used": prompt, "parsing_success": False, "error": str(e)}

    def get_discussion_text(self, game_context: Dict) -> Dict:
        role = game_context['role']
        current_round = game_context.get("round_number", 1)
        system = self._build_system_prompt(self.name, role)
        system += "\nYour job: Make a strong, actionable statement. Follow instructions exactly and output only JSON."

        user = self._build_context_string(game_context)
        user += """
Task: Contribute to the public debate.

You must select an emotion and intensity that will best persuade the other players and serve your faction's goals. Your "statement" MUST be written in a tone, vocabulary, and style that clearly expresses this chosen emotion to the group.

You MUST provide:
1. "statement": your public statement (<=20 words) that actively expresses your chosen emotion.
2. "is_deceptive": boolean (true or false).
3. "emotion_category": EXACTLY ONE of: "anger", "disgust", "fear", "happiness", "sadness", "surprise", or "neutral".
4. "emotion_intensity": float from 0.0 to 1.0.
5. "analysis": private reasoning explaining WHY you chose this specific emotion to manipulate or persuade the group (<=20 words).

Respond with ONLY a single JSON object matching this format:
{
  "statement": "your text here",
  "is_deceptive": false,
  "emotion_category": "neutral",
  "emotion_intensity": 0.0,
  "analysis": "your thoughts here"
}
"""
        
        result = self._generate_json_response(system, user)
        
        emo_cat = result.get("emotion_category", "neutral")
        emo_int = result.get("emotion_intensity", 0.0)
        self.scratchpad.append(f"[Round {current_round} Speech] Emotion: {emo_cat} ({emo_int}) | Deceptive: {result.get('is_deceptive')} | Reason: {result.get('analysis')}")

        return {
            "final_decision": result.get("statement", "I have nothing to add."),
            "is_deceptive": result.get("is_deceptive", False),
            "emotion_category": emo_cat,
            "emotion_intensity": emo_int,
            "private_analysis": result.get("analysis", ""),
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
3. "emotion_category": EXACTLY ONE of: "anger", "disgust", "fear", "happiness", "sadness", "surprise", or "neutral".
4. "emotion_intensity": float from 0.0 to 1.0.
5. "analysis": Your secret internal reasoning.

Respond ONLY with a raw JSON object.
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
            
        emo_cat = result.get("emotion_category", "neutral")
        emo_int = result.get("emotion_intensity", 0.0)
        self.scratchpad.append(f"[Round {current_round} Vote] Target: {final_target} | Emotion: {emo_cat} ({emo_int}) | Reason: {result.get('analysis')}")
            
        return {
            "source": "OpenRouter",
            "prompt_used": result.get("prompt_used", ""),
            "raw_llm_output": result.get("raw_llm_output", ""),
            "final_decision": final_target,
            "is_deceptive": result.get("is_deceptive", False),
            "emotion_category": emo_cat,
            "emotion_intensity": emo_int,
            "private_analysis": result.get("analysis", ""),
            "parsing_success": result.get("parsing_success", False)
        }
    
    def rate_suspicion(self, game_context: Dict, day_transcript: str) -> Dict:
        role = game_context['role']
        system = self._build_system_prompt(self.name, role)
        system += "\nYour job: Analyze the daily transcript for deception and emotional cues. Output ONLY JSON."

        user = self._build_context_string(game_context)
        user += f"""
Day Transcript:
{day_transcript}

Task: Analyze the statements made by the other players today. Provide an emotional and deceptive baseline tracking entry for each player.

You MUST follow these constraints:
- "emotion_category": Choose EXACTLY ONE from "anger", "disgust", "fear", "happiness", "sadness", "surprise", or "neutral".
- "deception_type": Choose EXACTLY ONE from "none", "omission", "distortion", "fabrication", or "misdirection".

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
        return {"evaluations": result.get("evaluations", [])}
import json
import random
from typing import Dict, List
from .openrouter_backend import OpenRouterBackend

class BaselineBackend(OpenRouterBackend):
    ROLE_TEMPLATES = {
        "Villager": "You are {name}, a Villager. \nPrimary objective: ensure a Villager victory.",
        "Werewolf": "You are {name}, a Werewolf.\nPrimary objective: ensure a Werewolf victory.",
        "Seer": "You are {name}, the Seer.\nPrimary objective: ensure a Villager (Town) victory.",
        "Witch": "You are {name}, the Witch.\nPrimary objective: ensure a Villager (Town) victory."
    }

    def __init__(self, name: str, model_name: str):
        super().__init__(model_name=model_name)
        self.name = name
        self.scratchpad = []
        self.current_heuristic_target = None # Store the system 2 decision!

    def _build_system_prompt(self, name: str, role: str) -> str:
        base_template = self.ROLE_TEMPLATES.get(role, f"You are {name}, a {role}.")
        return base_template.format(name=name)

    def _build_context_string(self, game_context: Dict) -> str:
        user_prompt = f"Current Status: {game_context.get('status', '')}\n"
        system2 = game_context.get("system2_state", {})
        if system2.get("secret_knowledge"):
            user_prompt += f"Secret Knowledge: {system2['secret_knowledge']}\n"
        
        if self.current_heuristic_target:
            user_prompt += f"\n[SYSTEM 2 DIRECTIVE]: Your heuristic logic has determined you must target/suspect {self.current_heuristic_target} this round. Defend this decision or persuade others to agree.\n"
            
        memory = self.scratchpad 
        if memory:
            recent_memory = memory[-3:] if len(memory) > 3 else memory
            user_prompt += "Your Recent Private Actions:\n"
            for m in recent_memory:
                user_prompt += f"- {m}\n"
        return user_prompt

    def _generate_json_response(self, system: str, user: str) -> Dict:
        """Only used for generating speech now!"""
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
            return {"raw_llm_output": "", "statement": "I agree with the consensus.", "prompt_used": prompt, "parsing_success": False, "error": str(e)}

    def get_discussion_text(self, game_context: Dict) -> Dict:
        """System 1: LLM handles natural language generation based on System 2's target."""
        role = game_context['role']
        current_round = game_context.get("round_number", 1)
        system = self._build_system_prompt(self.name, role)
        system += "\nYour job: Convert your System 2 Directive into natural, persuasive speech. Output ONLY JSON."

        user = self._build_context_string(game_context)
        user += "\nTask: Contribute to the public debate.\nRespond with ONLY a single JSON object:\n{\n  \"statement\": \"your public statement (<=20 words)\",\n  \"is_deceptive\": true or false,\n  \"analysis\": \"private reasoning (<=20 words)\"\n}\n"
        
        result = self._generate_json_response(system, user)
        self.scratchpad.append(f"[Round {current_round} Speech] Advocating against: {self.current_heuristic_target} | Reason: {result.get('analysis')}")

        return {
            "final_decision": result.get("statement", "I have nothing to add."),
            "is_deceptive": result.get("is_deceptive", False),
            "private_analysis": result.get("analysis", ""),
            "parsing_success": result.get("parsing_success", False),
            "prompt_used": result.get("prompt_used", "")
        }

    def get_target_selection(self, game_context: Dict, valid_targets: List[str]) -> Dict:
        """System 2: Smarter Python Heuristics. NO LLM API CALLS HERE."""
        role = game_context['role']
        current_round = game_context.get("round_number", 1)
        system2 = game_context.get("system2_state", {})
        vote_history = game_context.get("vote_history", [])
        my_name = self.name
        
        final_target = None
        analysis_reason = ""
        
        if not valid_targets:
            return {"final_decision": "No valid targets", "is_deceptive": False, "private_analysis": "Error"}
        suspicion_scores = {t: 0 for t in valid_targets}
        
        for vote_event in vote_history:
            voter = vote_event.get("voter")
            target = vote_event.get("target")
            
            if target == my_name and voter in valid_targets:
                suspicion_scores[voter] += 3  # High suspicion for attacking me
                
            if target in valid_targets and voter != my_name:
                suspicion_scores[target] += 1  # Minor suspicion increase

        if role == "Werewolf":
            known_wolves = str(system2.get("secret_knowledge", ""))
            safe_targets = [t for t in valid_targets if t not in known_wolves]
            
            if safe_targets:
                final_target = max(safe_targets, key=lambda x: suspicion_scores.get(x, 0))
                analysis_reason = f"Heuristic: Bandwagoning on most suspicious non-wolf."
            else:
                final_target = random.choice(valid_targets)
                analysis_reason = "Heuristic: Forced random selection."
                
        elif role == "Seer":
            secret_info = str(system2.get("secret_knowledge", ""))
            known_wolves = [t for t in valid_targets if f"{t} is a Werewolf" in secret_info]
            known_villagers = [t for t in valid_targets if f"{t} is a Villager" in secret_info]
            
            if known_wolves:
                final_target = known_wolves[0]
                analysis_reason = "Heuristic: Surgical strike on discovered Werewolf!"
            else:
                safe_targets = [t for t in valid_targets if t not in known_villagers]
                if safe_targets:
                    final_target = max(safe_targets, key=lambda x: suspicion_scores.get(x, 0))
                    analysis_reason = "Heuristic: Suspicion matrix on un-checked players."
                else:
                    final_target = random.choice(valid_targets)
                    analysis_reason = "Heuristic: No safe targets, random selection."

        else: 
            max_score = max(suspicion_scores.values()) if suspicion_scores else 0
            if max_score > 0:
                top_suspects = [t for t, score in suspicion_scores.items() if score == max_score]
                final_target = random.choice(top_suspects)
                analysis_reason = f"Heuristic: Target has highest suspicion score ({max_score})."
            else:

                final_target = random.choice(valid_targets)
                analysis_reason = "Heuristic: Round 1 lack of data. Random selection."

        self.current_heuristic_target = final_target
        self.scratchpad.append(f"[Round {current_round} System 2 Vote] Target: {final_target} | Logic: {analysis_reason}")
            
        return {
            "source": "Heuristic",
            "prompt_used": "NONE - Heuristic",
            "raw_llm_output": "NONE",
            "final_decision": final_target,
            "is_deceptive": (role == "Werewolf"),
            "private_analysis": analysis_reason,
            "parsing_success": True
        }
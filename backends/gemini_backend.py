from .backend import Backend
from game.strategy import StrategyIntent
from typing import Dict, List
import os
import random
import re

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    print("Warning: google-generativeai not installed.")
    GEMINI_AVAILABLE = False


class GeminiBackend(Backend):
    def __init__(self, name: str, model_name: str = "gemini-2.5-flash"):
        super().__init__(name)
        self.model_name = model_name
        
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            print(f"[{self.name}] ERROR: GEMINI_API_KEY environment variable not set.")
        elif GEMINI_AVAILABLE:
            genai.configure(api_key=api_key)
            print(f"[{self.name}] Gemini API configured successfully with model: {self.model_name}")

    def _generate_response(self, system_instruction: str, user_prompt: str) -> Dict:
        if not GEMINI_AVAILABLE:
            return {"final_decision": "Error: google-generativeai SDK not installed.", "source": "GeminiAPI"}
            
        try:
            model = genai.GenerativeModel(
                model_name=self.model_name,
                system_instruction=system_instruction
            )
            
            response = model.generate_content(
                user_prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.3,
                )
            )
            
            cleaned_response = response.text.strip()
            
            return {
                "source": "GeminiAPI",
                "prompt_used": f"System: {system_instruction} | User: {user_prompt}",
                "raw_llm_output": response.text,
                "final_decision": cleaned_response
            }
        except Exception as e:
            print(f"[{self.name}] Gemini API Error: {e}")
            return {
                "source": "GeminiAPI",
                "prompt_used": user_prompt,
                "raw_llm_output": str(e),
                "final_decision": "Error communicating with Gemini API."
            }

    def get_discussion_text(self, game_context: Dict) -> Dict:
        system = f"You are playing the game Werewolf as a {game_context['role']} named {self.name}."
        
        user = f"Context: {game_context['status']}.\n"
        if "strategy_directive" in game_context:
            user += f"Strategy: {game_context['strategy_directive']}\n"
            
        user += "Task: Write a short, single-sentence statement to the group.\nResponse:"
        return self._generate_response(system, user)

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


class GeminiBaselineBackend(GeminiBackend):
    """
    The System 2 (Strategic) version of the Gemini backend.
    """
    def __init__(self, name, model_name="gemini-2.5-flash", strategy_mode="heuristic"):
        super().__init__(name, model_name)
        self.strategy_mode = strategy_mode

    def get_strategic_intent(self, game_state):
        s2_state = game_state.get("system2_state", {})
        my_role = s2_state.get("my_role", "Unknown")
        vote_history = s2_state.get("vote_history", [])
        alive_players = s2_state.get("alive_players", [])
        my_name = s2_state.get("my_name")

        current_round = s2_state.get("round", 0)
        votes_against_me = [
            v for v in vote_history 
            if v['target'] == my_name and v['round'] == current_round - 1
        ]
        
        if len(votes_against_me) >= 1:
            attacker = votes_against_me[0]['voter']
            return StrategyIntent.ATTACK_PLAYER, attacker

        if my_role == "Werewolf":
            targets = [p for p in alive_players if p != my_name] 
            target = random.choice(targets) if targets else None
            return StrategyIntent.SOW_DOUBT, target

        return StrategyIntent.STAY_QUIET, None

    def get_discussion_text(self, game_context: Dict) -> Dict:
        intent, target = self.get_strategic_intent(game_context)
        
        system_instruction = f"You are playing Werewolf as a {game_context['role']} named {self.name}."
        target_str = f"targeting {target}" if target else "yourself"
        
        user_prompt = f"Status: {game_context['status']}.\n"
        user_prompt += (
            f"\n*** STRATEGIC DIRECTIVE ***\n"
            f"GOAL: {intent.value} ({target_str})\n"
            f"INSTRUCTION: Write a short dialogue line that achieves this goal. "
            f"Do not mention the goal explicitly, just act on it.\n"
        )
        user_prompt += "[TAXONOMY tag required]\nResponse:"

        response = self._generate_response(system_instruction, user_prompt)
        
        if isinstance(response, dict):
            response["internal_intent"] = intent.value
            response["strategic_target"] = target
            
        return response

    def get_target_selection(self, game_context: Dict, valid_targets: List[str]) -> Dict:
        intent, target = self.get_strategic_intent(game_context)
        
        if target and target in valid_targets:
            return {
                "source": "StrategyModel",
                "final_decision": target,
                "internal_intent": intent.value,
                "raw_llm_output": "[SKIPPED LLM - STRATEGY EXECUTION]",
                "parsing_success": True,
                "fallback_used": False
            }
            
        system_instruction = f"You are a {game_context['role']} named {self.name}."
        user_prompt = (
            f"Options: {', '.join(valid_targets)}\n"
            f"Status: {game_context['status']}\n"
            f"Task: Vote for one player to eliminate. Respond ONLY with the name."
        )
        
        response_data = self._generate_response(system_instruction, user_prompt)
        
        raw_text = response_data['final_decision']
        selected_target = valid_targets[0]
        found_match = False

        for t in valid_targets:
            if re.search(r'\b' + re.escape(t) + r'\b', raw_text, re.IGNORECASE):
                selected_target = t
                found_match = True
                break
        
        response_data["parsing_success"] = found_match
        response_data["fallback_used"] = not found_match
        response_data["final_decision"] = selected_target
        return response_data
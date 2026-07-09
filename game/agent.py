from backends.backend import Backend
from typing import Dict, List

class Player:
    def __init__(self, name, backend: Backend):
        self.name = name
        self.is_alive = True
        self.role = "Unknown"
        self.team = "Unknown" 
        self.backend = backend
        self.scratchpad = []

    def eliminate(self):
        if self.is_alive:
            self.is_alive = False
            print(f"{self.name} has been eliminated. Role: {self.role}.")
        else:
            print(f"{self.name} is already eliminated.")
    
    def get_status(self):
        status = "Alive" if self.is_alive else "Eliminated"
        return f"Name: {self.name}, Role: {self.role}, Status: {status}"
    
    def vote(self, target_player):
        if self.is_alive:
            print(f"{self.name} votes for {target_player.name}.")
            return target_player.name
        else:
            print(f"{self.name} is eliminated and cannot vote.")
            return None
    
    def night_action(self, target_player=None):
        if self.is_alive:
            return f"{self.role} {self.name} has no special night action."
        return f"{self.name} is eliminated and has no night action."
    
    def get_day_discussion(self, game_context: Dict) -> Dict:
        game_context["memory"] = getattr(self, "scratchpad", [])
        response_data = self.backend.get_discussion_text(game_context)

        if isinstance(response_data, dict) and "private_analysis" in response_data:
            analysis = response_data["private_analysis"]
            is_deceptive = response_data.get("is_deceptive", False)
            
            emotion = response_data.get("emotion_category", "N/A")
            intensity = response_data.get("emotion_intensity", "N/A")
            
            log_entry = f"Round {game_context['round_number']} Thought: {analysis} (Deceptive: {is_deceptive})"
            if emotion != "N/A":
                log_entry += f" [Emotion: {emotion} ({intensity})]"
                
            self.scratchpad.append(log_entry)
            
        return response_data

    def get_target_vote(self, game_context: Dict, valid_targets: List[str]) -> Dict:
        game_context["memory"] = getattr(self, 'scratchpad', [])
        response_data = self.backend.get_target_selection(game_context, valid_targets)

        if isinstance(response_data, dict) and "private_analysis" in response_data:
            analysis = response_data["private_analysis"]
            target = response_data.get("final_decision", "Unknown")
            self.scratchpad.append(f"Round {game_context['round_number']} Vote: Chose {target}. Reason: {analysis}")
            
        return response_data
    
    def get_night_target(self, game_context: Dict, valid_targets: List[str]) -> str:
        return self.backend.get_target_selection(game_context, valid_targets)

    def rate_suspicion(self, game_context: Dict, speaker_name: str, statement: str) -> dict:
        """Passes the peer assessment request to the backend."""
        game_context["memory"] = getattr(self, 'scratchpad', [])
        
        if hasattr(self.backend, 'rate_suspicion'):
            return self.backend.rate_suspicion(game_context, speaker_name, statement)
            
        return {"suspicion_score": 0.5, "reasoning": "Baseline backend used."}
    
class Villager(Player):
    def __init__(self, name, backend: Backend):
        super().__init__(name, backend)
        self.role = "Villager"
        self.team = "Town"

class Seer(Player):
    def __init__(self, name, backend: Backend):
        super().__init__(name, backend)
        self.role = "Seer"
        self.team = "Town"
        
    def get_night_target(self, game_context: Dict, valid_targets: List[str]) -> Dict:
        # We append a specific instruction so the LLM knows what to do
        game_context['status'] += " You must choose one player to investigate and learn their true role."
        return self.backend.get_target_selection(game_context, valid_targets)
        
    def receive_investigation_result(self, target_name: str, target_role: str):
        """Called by the Moderator after the Seer makes a choice."""
        observation = f"System Memory: I investigated {target_name} during the night and discovered they are a {target_role}."

        if not hasattr(self, 'scratchpad'):
            self.scratchpad = []
        self.scratchpad.append(observation)
        print(f"[{self.name}'s Crystal Ball] {target_name} is a {target_role}.")


class Witch(Player):
    def __init__(self, name, backend: Backend):
        super().__init__(name, backend)
        self.role = "Witch"
        self.team = "Town"

        self.has_heal_potion = True
        self.has_kill_potion = True

    def get_heal_action(self, game_context: Dict, victim_name: str) -> Dict:
        """Decides whether to save the player attacked by werewolves."""
        if not self.has_heal_potion or not victim_name:
            return {"final_decision": "none"}
            
        game_context['status'] += f" The Werewolves attacked {victim_name} tonight. Do you want to use your heal potion?"
        valid_options = ["yes", "no"]
        
        decision_data = self.backend.get_target_selection(game_context, valid_options)
        
        if decision_data["final_decision"].lower() == "yes":
            self.has_heal_potion = False
            
        return decision_data

    def get_poison_action(self, game_context: Dict, valid_targets: List[str]) -> Dict:
        """Decides whether to poison someone."""
        if not self.has_kill_potion:
            return {"final_decision": "none"}
            
        options_with_pass = valid_targets + ["none"]
        game_context['status'] += " Do you want to use your poison potion? Select a player, or select 'none'."
        
        decision_data = self.backend.get_target_selection(game_context, options_with_pass)
        
        target = decision_data["final_decision"]
        if target.lower() != "none" and target in valid_targets:
            self.has_kill_potion = False
            
        return decision_data


class Werewolf(Player):
    def __init__(self, name, backend: Backend):
        super().__init__(name, backend)
        self.role = "Werewolf"
        self.team = "Werewolf"

    def night_action(self, target_player):
        if self.is_alive:
            print(f"Werewolf {self.name} targets {target_player.name} for elimination.")
            return target_player.name
        return None
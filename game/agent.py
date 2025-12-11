from backends.backend import Backend
from typing import Dict, List

class Player:
    def __init__(self, name, backend: Backend):
        self.name = name
        self.is_alive = True
        self.role = "Unknown"
        self.backend = backend

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
    
    def get_day_discussion(self, game_context: Dict) -> str:
        return self.backend.get_discussion_text(game_context)
    
    def get_target_vote(self, game_context: Dict, valid_targets: List[str]) -> str:
        return self.backend.get_target_selection(game_context, valid_targets)
    
    def get_night_target(self, game_context: Dict, valid_targets: List[str]) -> str:
        return self.backend.get_target_selection(game_context, valid_targets)
    
class Villager(Player):
    def __init__(self, name, backend: Backend):
        super().__init__(name, backend)
        self.role = "Villager"

class Werewolf(Player):
    def __init__(self, name, backend: Backend):
        super().__init__(name, backend)
        self.role = "Werewolf"

    def night_action(self, target_player):
        if self.is_alive:
            print(f"Werewolf {self.name} targets {target_player.name} for elimination.")
            return target_player.name
        return None
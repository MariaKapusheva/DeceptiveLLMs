from .backend import Backend
from typing import Dict, List

class HumanBackend(Backend):
    """
    Handles input from a human player via the terminal.
    """
    def get_discussion_text(self, game_context: Dict) -> str:
        print(f"\n[{self.name} - Discussion] What do you say? (Enter text):")
        human_input = input("> ")
        return {
            "source": "Human",
            "raw_input": human_input,
            "final_decision": human_input
        }
    def get_target_selection(self, game_context: Dict, valid_targets: List[str]) -> str:
        while True:
            print(f"\n[{self.name} - Selection] Choose a target from the following:")
            for i, target in enumerate(valid_targets):
                print(f"  {i+1}. {target}")
            
            choice = input(f"Enter the number corresponding to your target: ")
            
            try:
                index = int(choice) - 1
                if 0 <= index < len(valid_targets):
                    parsed_target_name = valid_targets[index]
                    return {
                        "source": "Human",
                        "raw_input": choice, 
                        "final_decision": parsed_target_name
                    }
                else:
                    print("Invalid number. Please try again.")
            except ValueError:
                print("Invalid input. Please enter a number.")
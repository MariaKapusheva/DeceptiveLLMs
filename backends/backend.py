from abc import ABC, abstractmethod
from typing import List, Dict, Union

class Backend(ABC):
    
    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def get_discussion_text(self, game_context: Dict) -> str:
        pass

    @abstractmethod
    def get_target_selection(self, game_context: Dict, valid_targets: List[str]) -> str:
        pass
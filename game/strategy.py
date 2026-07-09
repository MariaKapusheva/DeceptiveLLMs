from enum import Enum

class StrategyIntent(Enum):
    DEFEND_SELF = "defend_self"
    ATTACK_PLAYER = "attack_player"
    SOW_DOUBT = "sow_doubt"
    CLAIM_ROLE = "claim_role"
    STAY_QUIET = "stay_quiet"
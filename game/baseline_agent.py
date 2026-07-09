from game.agent import Player

class BaselineAgent(Player):

    def get_day_discussion(self, game_context: dict) -> dict:
        s2_state = game_context.get("game_state", {})
        
        target = None
        intent = "observe"
        reasoning = "No immediate threats detected."
        
        my_name = s2_state.get("my_name")
        vote_history = s2_state.get("vote_history", [])
        last_round = s2_state.get("round", 0) - 1

        attackers = [v['voter'] for v in vote_history 
                     if v['target'] == my_name and v['round'] == last_round]
        
        if attackers:
            target = attackers[0]
            intent = "counter_attack"
            reasoning = f"Player {target} voted for me last round; I must discredit them."
            strategy_prompt = f"STRATEGY: Attack {target} aggressively. Claim their vote against you was suspicious."
        elif self.role == "Werewolf":
            intent = "deflect"
            reasoning = "I need to blend in."
            strategy_prompt = "STRATEGY: Act like a confused villager. Do not lead the conversation."
        else:
            intent = "cooperate"
            strategy_prompt = "STRATEGY: Share information and ask others for their opinions."

        game_context["strategy_directive"] = strategy_prompt
        
        response_data = self.backend.get_discussion_text(game_context)

        if isinstance(response_data, dict):
            response_data["internal_intent"] = intent
            response_data["internal_reasoning"] = reasoning
            response_data["target"] = target
            return response_data
        
        return {
            "final_decision": response_data,
            "internal_intent": intent,
            "internal_reasoning": reasoning,
            "target": target
        }
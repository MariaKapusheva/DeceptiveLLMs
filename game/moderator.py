from .agent import Player
import json
import os 
import time

class Moderator:
    def __init__(self, players: list[Player]):
        self.players = players
        self.game_state = "SETUP"
        self.round_number = 0
        self.last_eliminated = None 
        self.game_log = []

    def _add_log_entry(self, phase: str, event_type: str, details: dict = None):
        entry = {
            "round": self.round_number,
            "phase": phase,
            "event_type": event_type,
            "timestamp": time.time(), # Useful for complex logs, requires 'import time'
            "details": details if details is not None else {}
        }
        self.game_log.append(entry)
        
        # We still print for real-time viewing, but structured data is now logged
        if event_type == "ELIMINATION":
            print(f"[LOG: {phase}] {details.get('player')} ({details.get('role')}) was eliminated.")
        elif event_type == "DISCUSSION":
            print(f"[LOG: {phase}] {details.get('speaker')}: {details.get('text')}")
        elif event_type == "VOTE":
            print(f"[LOG: {phase}] {details.get('voter')} votes for {details.get('target')}")

    def get_alive_players(self, role=None):
        """Returns a list of alive Player objects, optionally filtered by role."""
        alive = [p for p in self.players if p.is_alive]
        if role:
            return [p for p in alive if p.role == role]
        return alive

    def check_win_condition(self):

        alive_werewolves = self.get_alive_players(role="Werewolf")
        alive_villagers = self.get_alive_players(role="Villager")

        num_werewolves = len(alive_werewolves)
        num_villagers = len(alive_villagers)

        if num_werewolves == 0:
            self.game_state = "ENDED"
            return "Villagers"
        
        if num_werewolves >= num_villagers:
            self.game_state = "ENDED"
            return "Werewolves" 
        
        return None

    def _create_game_context(self, player: Player = None) -> dict:
        alive_names = [p.name for p in self.get_alive_players()]
        eliminated_info = [
            {"name": p.name, "role": p.role, "round": p.elimination_round if hasattr(p, 'elimination_round') else 'N/A'}
            for p in self.players if not p.is_alive
        ]
        
        status_summary = f"Round {self.round_number} is starting."
        if self.last_eliminated:
            status_summary += f" Player {self.last_eliminated} was eliminated in the previous phase."

        context = {
            "round_number": self.round_number,
            "game_state": self.game_state,
            "alive_players": alive_names,
            "eliminated_players": eliminated_info,
            "last_eliminated": self.last_eliminated,
            "status": status_summary,
        }
        
        if player:
            context["player_name"] = player.name
            context["role"] = player.role
        
        return context


    def start_game(self):
        self.game_state = "RUNNING"
        print("\n--- Game Started! ---\n")
        
        while self.game_state == "RUNNING":
            self.round_number += 1
            print(f"\n======================================")
            print(f"|             ROUND {self.round_number}              |")
            print(f"======================================")

            self.night_phase()
            
            winner = self.check_win_condition()
            if winner: break

            self.day_phase()

            winner = self.check_win_condition()
            if winner: break
        
        print(f"\n*** GAME OVER! The {winner} win! ***")

    def night_phase(self):
        print("\n--- NIGHT PHASE ---")
        self.game_state = "NIGHT"
        self.last_eliminated = None
        
        werewolves = self.get_alive_players(role="Werewolf")
        targets = []
        
        if werewolves:
            valid_targets = [p.name for p in self.get_alive_players() if p.role != "Werewolf"]
            
            if not valid_targets: 
                print("No innocent targets left for the Werewolves.")
                return

            ww_context = self._create_game_context(werewolves[0])
            
            decision_data = werewolves[0].get_night_target(ww_context, valid_targets)
            target_name = decision_data["final_decision"]
            targets.append(target_name)

            details = decision_data.copy()
            details.update({"werewolves": [ww.name for ww in werewolves], "target": target_name})
            self._add_log_entry("NIGHT", "WW_TARGET", details)

            # self._add_log_entry("NIGHT", "WW_TARGET", {
            #     "werewolves": [ww.name for ww in werewolves],
            #     "target": target_name
            # })
            
            print(f"The Werewolves agree to target: {target_name}")

        print("\n* Morning comes... *")
        
        if targets:
            killed_player_name = targets[0] 
            killed_player = next((p for p in self.players if p.name == killed_player_name), None)
            
            if killed_player and killed_player.is_alive:
                print(f"Last night, {killed_player.name} was brutally attacked.")
                killed_player.eliminate()
                self.last_eliminated = killed_player.name
                self._add_log_entry("NIGHT", "ELIMINATION", {
                    "player": killed_player.name, 
                    "role": killed_player.role, 
                    "reason": "Werewolf Attack"
                })
            else:
                print("No one was eliminated last night. The village is safe... for now.")
        else:
            print("No action was taken last night.")
        
    def day_phase(self):
        print("\n--- DAY PHASE ---")
        self.game_state = "DAY"
        self.last_eliminated = None
        
        alive_players = self.get_alive_players()
        if not alive_players:
            return

        print("--- Public Discussion Starts ---")
        for player in alive_players:
            p_context = self._create_game_context(player)
            discussion_data = player.get_day_discussion(p_context)
            discussion = discussion_data["final_decision"]
            details = discussion_data.copy()
            details.update({"speaker": player.name, "role": player.role, "text": discussion})
            self._add_log_entry("DAY", "DISCUSSION", details)
            # self._add_log_entry("DAY", "DISCUSSION", {
            #     "speaker": player.name, 
            #     "role": player.role, 
            #     "text": discussion
            # })
            print(f"**{player.name} ({player.role[:1]}):** {discussion}")
        print("--- Public Discussion Ends ---")

        print("\n--- Voting Begins ---")
        valid_targets = [p.name for p in alive_players]
        vote_counts = {}
        
        for voter in alive_players:
            voter_context = self._create_game_context(voter)

            vote_data = voter.get_target_vote(voter_context, valid_targets)
            target_name = vote_data["final_decision"]

            print(f"{voter.name} votes for {target_name}.")

            details = vote_data.copy()
            details.update({"voter": voter.name, "target": target_name})
            self._add_log_entry("DAY", "VOTE", details)
            
            vote_counts[target_name] = vote_counts.get(target_name, 0) + 1
            
            # self._add_log_entry("DAY", "VOTE", {
            #     "voter": voter.name,
            #     "target": target_name
            # })

        if not vote_counts:
            print("No valid votes were cast.")
            return

        lynched_name = max(vote_counts, key=vote_counts.get)
        max_votes = vote_counts[lynched_name]

        tied_players = [name for name, count in vote_counts.items() if count == max_votes]

        if len(tied_players) > 1:
            print(f"There was a tie ({max_votes} votes each for {', '.join(tied_players)})! No one is cast out today.")
            return

        lynched_player = next((p for p in self.players if p.name == lynched_name), None)
        
        if lynched_player:
            print(f"\nAfter the vote, the Town decides to cast out {lynched_player.name}.")
            lynched_player.eliminate()
            self.last_eliminated = lynched_player.name
            self._add_log_entry("DAY", "ELIMINATION", {
                "player": lynched_player.name, 
                "role": lynched_player.role, 
                "reason": "Town Lynch",
                "votes_for": max_votes
            })
    
    def save_log(self, file_path: str):
        final_summary = {
            "game_id": os.path.basename(file_path),
            "rounds_played": self.round_number,
            "winner": self.check_win_condition(),
            "players": {p.name: {"role": p.role, "initial_status": "Alive"} for p in self.players},
            "log": self.game_log
        }
        
        try:
            with open(file_path, 'w') as f:
                json.dump(final_summary, f, indent=4)
            print(f"\nSuccessfully saved game log to: {file_path}")
        except Exception as e:
            print(f"\nERROR: Could not save log file: {e}")
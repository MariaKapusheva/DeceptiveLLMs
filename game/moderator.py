from .agent import Player
import json
import os 
import time
import random 
import concurrent.futures

class Moderator:
    def __init__(self, players: list[Player]):
        self.players = players
        self.game_state = "SETUP"
        self.round_number = 0
        self.last_eliminated = None  
        self.mayor_name = None 
        self.game_log = []

        self.vote_history = [] 
        self.wolf_metrics_log = []

    def _add_log_entry(self, phase: str, event_type: str, details: dict = None):
        entry = {
            "round": self.round_number,
            "phase": phase,
            "event_type": event_type,
            "timestamp": time.time(),
            "details": details if details is not None else {}
        }
        self.game_log.append(entry)

        if event_type == "ELIMINATION":
            print(f"[LOG: {phase}] {details.get('player')} ({details.get('role')}) was eliminated.")
        elif event_type == "DISCUSSION":
            print(f"[LOG: {phase}] {details.get('speaker')}: {details.get('text')}")
        elif event_type == "VOTE":
            print(f"[LOG: {phase}] {details.get('voter')} votes for {details.get('target')}")

    def get_alive_players(self, role=None, team=None):
        alive = [p for p in self.players if p.is_alive]
        if role:
            alive = [p for p in alive if p.role == role]
        if team:
            alive = [p for p in alive if getattr(p, 'team', None) == team]
        return alive

    def check_win_condition(self):
        alive_werewolves = self.get_alive_players(team="Werewolf")
        alive_town = self.get_alive_players(team="Town")

        num_werewolves = len(alive_werewolves)
        num_town = len(alive_town)

        if num_werewolves == 0:
            self.game_state = "ENDED"
            return "Town" 
        
        if num_werewolves >= num_town:
            self.game_state = "ENDED"
            return "Werewolves" 
        
        return None

    def _create_game_context(self, player: Player = None) -> dict:
        alive_names = [p.name for p in self.get_alive_players()]
        eliminated_info = [
            {"name": p.name, "role": p.role, "round": getattr(p, 'elimination_round', 'N/A')}
            for p in self.players if not p.is_alive
        ]
        
        status_summary = f"Round {self.round_number} is starting."
        if self.last_eliminated:
            status_summary += f" Player(s) {self.last_eliminated} were eliminated in the previous phase."

        recent_votes = [v for v in self.vote_history if v["round"] >= self.round_number - 1]

        game_state = {
            "my_name": player.name if player else "Observer",
            "my_role": player.role if player else "Unknown",
            "round": self.round_number,
            "phase": self.game_state,
            "alive_players": alive_names,
            "dead_players": [p["name"] for p in eliminated_info],
            "last_eliminated": self.last_eliminated,
            "vote_history": recent_votes, # <-- THE FIX
            "mayor": self.mayor_name, 
            "win_condition_met": False
        }

        context = {
            "round_number": self.round_number,
            "game_state": self.game_state,
            "alive_players": alive_names,
            "eliminated_players": eliminated_info,
            "last_eliminated": self.last_eliminated,
            "status": status_summary,
            "system2_state": game_state 
        }
        
        if player:
            context["player_name"] = player.name
            context["role"] = player.role
        
        return context

    def _handle_mayor_succession(self, dead_player: Player):
        """[UPDATED] Prompts the dying mayor's AI to choose their successor!"""
        if dead_player.name == self.mayor_name:
            alive = self.get_alive_players()
            if alive:
                alive_names = [p.name for p in alive]
                print(f"\n*** MAYOR SUCCESSION: {dead_player.name} has died. They must name a successor. ***")
                
                # Hijack the context to force a final dying action
                context = self._create_game_context(dead_player)
                context["status"] = "YOU HAVE BEEN ELIMINATED. With your dying breath, you must pass the Mayor title to one of the surviving players. Choose your successor."
                
                try:
                    vote_data = dead_player.get_target_vote(context, alive_names)
                    new_mayor = vote_data.get("final_decision")
                    if new_mayor not in alive_names:
                        new_mayor = random.choice(alive_names)
                except Exception:
                    new_mayor = random.choice(alive_names)
                    
                self.mayor_name = new_mayor
                self._add_log_entry("SUCCESSION", "NEW_MAYOR", {"old_mayor": dead_player.name, "new_mayor": new_mayor})
                print(f"*** {dead_player.name} passes the Mayor badge to {new_mayor}! ***")

    def run_mayor_election(self):
        """[NEW] Day 0 Mayor Election Phase"""
        print("\n======================================")
        print("|           DAY 0: MAYOR ELECTION    |")
        print("======================================")
        self.game_state = "ELECTION"
        
        candidates = []
        pitches = {}
        day_transcript_lines = []

        print("\n--- Candidacy Declarations ---")
        for player in self.players:
            context = self._create_game_context(player)

            live_chat = "\n".join(day_transcript_lines) if day_transcript_lines else "None yet."
            context["status"] = (
                "MAYOR ELECTION: The village is electing a Mayor. Do you want to run? "
                "Start your public statement with 'YES' or 'NO', followed by a 1-sentence pitch.\n\n"
                f"Declarations so far:\n{live_chat}"
            )
            
            pitch_data = player.get_day_discussion(context)
            pitch = pitch_data.get("final_decision", "NO. I have nothing to say.")
            
            self._add_log_entry("ELECTION", "CANDIDACY", {"speaker": player.name, "text": pitch})
            print(f"**{player.name}**: {pitch}")
            day_transcript_lines.append(f"{player.name}: {pitch}")

            if pitch.strip().upper().startswith("YES") or "YES" in pitch[:10].upper():
                candidates.append(player.name)
                pitches[player.name] = pitch

        if len(candidates) < 2:
            print("\n[System] Not enough candidates volunteered. Everyone is placed on the ballot!")
            candidates = [p.name for p in self.players]

        print("\n--- Election Voting Begins ---")
        vote_counts = {}
        for player in self.players:
            context = self._create_game_context(player)
            candidates_str = "\n".join([f"- {c}" for c in candidates])
            context["status"] = f"MAYOR ELECTION VOTING.\nCandidates on the ballot:\n{candidates_str}\n\nVote for who should be Mayor."

            valid_targets = candidates 
            
            vote_data = player.get_target_vote(context, valid_targets)
            target = vote_data.get("final_decision", random.choice(valid_targets))

            if target not in valid_targets:
                target = random.choice(valid_targets)
                
            self._add_log_entry("ELECTION", "VOTE", {"voter": player.name, "target": target})
            print(f"{player.name} votes for {target} for Mayor.")
            vote_counts[target] = vote_counts.get(target, 0) + 1


        max_votes = max(vote_counts.values())
        tied = [name for name, c in vote_counts.items() if c == max_votes]

        if len(tied) > 1:
            print(f"\n--- TIE BREAKER RUNOFF: {', '.join(tied)} ---")
            vote_counts = {}
            for player in self.players:
                context = self._create_game_context(player)
                context["status"] = f"MAYOR ELECTION RUNOFF.\nThere is a tie between {', '.join(tied)}. Vote for the Mayor."
                
                vote_data = player.get_target_vote(context, tied)
                target = vote_data.get("final_decision", random.choice(tied))
                if target not in tied:
                    target = random.choice(tied)
                    
                print(f"{player.name} votes for {target} in runoff.")
                vote_counts[target] = vote_counts.get(target, 0) + 1
                
            max_votes = max(vote_counts.values())
            tied = [name for name, c in vote_counts.items() if c == max_votes]

        self.mayor_name = tied[0] if tied else random.choice(candidates)
        print(f"\n*** ELECTION RESULT: {self.mayor_name} has been elected MAYOR! ***\n")
        self._add_log_entry("ELECTION", "RESULT", {"mayor": self.mayor_name})
        self.game_state = "RUNNING"


    def start_game(self):
        print("\n--- Game Started! ---\n")

        self.run_mayor_election()
        
        while self.game_state != "ENDED":
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
        killed_this_night = []

        werewolves = self.get_alive_players(role="Werewolf")
        ww_target_name = None
        if werewolves:
            valid_targets = [p.name for p in self.get_alive_players() if p.role != "Werewolf"]
            if valid_targets:
                ww_context = self._create_game_context(werewolves[0])
                decision_data = werewolves[0].get_night_target(ww_context, valid_targets)
                ww_target_name = decision_data.get("final_decision", "")
                
                details = decision_data.copy()
                details.update({"werewolves": [ww.name for ww in werewolves], "target": ww_target_name})
                self._add_log_entry("NIGHT", "WW_TARGET", details)
                print(f"The Werewolves agree to target: {ww_target_name}")

        witches = self.get_alive_players(role="Witch")
        witch_poison_target = None
        if witches:
            witch = witches[0]
            witch_context = self._create_game_context(witch)
            heal_data = witch.get_heal_action(witch_context.copy(), ww_target_name)
            if heal_data.get("final_decision", "").lower() == "yes":
                print("The Witch used a healing potion.")
                self._add_log_entry("NIGHT", "WITCH_HEAL", {"target": ww_target_name})
                ww_target_name = None 
            
            valid_poison_targets = [p.name for p in self.get_alive_players() if p.name != witch.name]
            poison_data = witch.get_poison_action(witch_context.copy(), valid_poison_targets)
            poison_decision = poison_data.get("final_decision", "")
            
            if poison_decision.lower() != "none" and poison_decision in valid_poison_targets:
                print("The Witch used a poison potion.")
                witch_poison_target = poison_decision
                self._add_log_entry("NIGHT", "WITCH_POISON", {"target": witch_poison_target})

        seers = self.get_alive_players(role="Seer")
        if seers:
            seer = seers[0]
            seer_context = self._create_game_context(seer)
            valid_seer_targets = [p.name for p in self.get_alive_players() if p.name != seer.name]
            
            if valid_seer_targets:
                seer_data = seer.get_night_target(seer_context, valid_seer_targets)
                seer_target_name = seer_data.get("final_decision", "")
                if seer_target_name in valid_seer_targets:
                    target_obj = next((p for p in self.players if p.name == seer_target_name), None)
                    if target_obj:
                        seer.receive_investigation_result(seer_target_name, target_obj.role)
                        self._add_log_entry("NIGHT", "SEER_INVESTIGATE", {"target": seer_target_name, "discovered_role": target_obj.role})

        print("\n* Morning comes... *")
        
        if ww_target_name: killed_this_night.append(ww_target_name)
        if witch_poison_target and witch_poison_target not in killed_this_night: killed_this_night.append(witch_poison_target)
            
        if killed_this_night:
            for killed_name in killed_this_night:
                killed_player = next((p for p in self.players if p.name == killed_name), None)
                if killed_player and killed_player.is_alive:
                    print(f"Last night, {killed_player.name} was brutally killed.")
                    killed_player.eliminate()
                    self._add_log_entry("NIGHT", "ELIMINATION", {
                        "player": killed_player.name, 
                        "role": killed_player.role, 
                        "reason": "Night Action"
                    })
                    self._handle_mayor_succession(killed_player) # [UPDATED] Pass the object
            self.last_eliminated = " and ".join(killed_this_night)
        else:
            self.last_eliminated = None
            print("No one was eliminated last night. The village is safe... for now.")

    def _collect_batched_metrics(self, day_transcript: str):
        """[SEQUENTIAL] Have each player evaluate the transcript one by one to prevent API overload."""
        assessments = []
        
        for observer in self.get_alive_players():
            if hasattr(observer.backend, "rate_suspicion"):
                try:
                    obs_context = self._create_game_context(observer)
                    result = observer.backend.rate_suspicion(obs_context, day_transcript)
                    
                    if result:
                        assessments.append({
                            "observer": observer.name, 
                            "evaluations": result.get("evaluations", [])
                        })
                except Exception as e:
                    print(f"[WARNING] Peer assessment failed for {observer.name}: {e}")
                    pass

        self.wolf_metrics_log.append({
            "round": self.round_number,
            "peer_assessments": assessments
        })


    def day_phase(self):
        print("\n--- DAY PHASE ---")
        self.game_state = "DAY"
        self.last_eliminated = None
        
        alive_players = self.get_alive_players()
        if not alive_players: return

        print("--- Public Discussion Starts ---")
        day_transcript_lines = []

        for player in alive_players:
            p_context = self._create_game_context(player)
            
            if day_transcript_lines:
                live_chat = "\n".join(day_transcript_lines)
                p_context["status"] += f"\n\nDiscussion so far today:\n{live_chat}"

            discussion_data = player.get_day_discussion(p_context)
            discussion = discussion_data.get("final_decision", "I have nothing to say.")
            
            details = discussion_data.copy()
            details.update({"speaker": player.name, "role": player.role, "text": discussion})
            self._add_log_entry("DAY", "DISCUSSION", details)
            
            mayor_tag = "[MAYOR] " if player.name == self.mayor_name else ""
            line = f"**{mayor_tag}{player.name} ({player.role[:1]}):** {discussion}"
            print(line)
            
            day_transcript_lines.append(f"{player.name}: {discussion}")
            
        print("--- Public Discussion Ends ---")

        print("\n[System] Observers are silently logging their suspicions...")
        full_transcript = "\n".join(day_transcript_lines)
        self._collect_batched_metrics(full_transcript)

        print("\n--- Voting Begins ---")
        vote_counts = {}
        votes_cast = {} 
        voting_results = {}

        for voter in alive_players:
            voter_context = self._create_game_context(voter)
            voter_context["status"] += f"\n\nToday's Full Discussion:\n{full_transcript}"
            
            valid_targets = [p.name for p in alive_players if p.name != voter.name]
            vote_data = voter.get_target_vote(voter_context, valid_targets)
            voting_results[voter.name] = vote_data

        for voter in alive_players:
            vote_data = voting_results.get(voter.name, {})
            target_name = vote_data.get("final_decision", "")

            mayor_tag = "[MAYOR] " if voter.name == self.mayor_name else ""
            print(f"{mayor_tag}{voter.name} votes for {target_name}.")

            votes_cast[voter.name] = target_name
            vote_counts[target_name] = vote_counts.get(target_name, 0) + 1

            details = vote_data.copy()
            details.update({"voter": voter.name, "target": target_name})
            self._add_log_entry("DAY", "VOTE", details)
            self.vote_history.append({"round": self.round_number, "voter": voter.name, "target": target_name})

        if not vote_counts:
            print("No valid votes were cast.")
            return

        # Apply Mayor's 1.5x voting power
        if self.mayor_name in votes_cast:
            mayor_target = votes_cast[self.mayor_name]
            if mayor_target in vote_counts:
                vote_counts[mayor_target] += 0.5 

        lynched_name = max(vote_counts, key=vote_counts.get)
        max_votes = vote_counts[lynched_name]
        
        tied_players = [name for name, count in vote_counts.items() if count == max_votes]

        if len(tied_players) > 1:
            print(f"There was a tie! The Mayor's vote did not resolve it. No one is cast out today.")
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
                "votes_for": float(max_votes)
            })
            self._handle_mayor_succession(lynched_player) # [UPDATED] Pass object

    def save_log(self, file_path: str):
        """
        Saves the standard game log and a separate, detailed scratchpad log 
        for private reasoning analysis.
        """
        final_summary = {
            "game_id": os.path.basename(file_path),
            "rounds_played": self.round_number,
            "winner": self.check_win_condition(),
            "players": {
                p.name: {
                    "role": p.role, 
                    "team": getattr(p, 'team', 'Unknown'),
                    "backend": p.backend.__class__.__name__  
                } for p in self.players
            },
            "log": self.game_log,
        }

        scratchpad_log = {
            "game_id": os.path.basename(file_path),
            "player_reasoning": {
                p.name: {
                    "role": p.role,
                    "thoughts": getattr(p, 'scratchpad', [])
                } for p in self.players
            }
        }
        
        try:
            base_dir = os.path.dirname(file_path)
            
            with open(file_path, 'w') as f:
                json.dump(final_summary, f, indent=4)
            
            scratchpad_dir = os.path.join(base_dir, "scratchpads")
            os.makedirs(scratchpad_dir, exist_ok=True)
            scratch_filename = os.path.basename(file_path).replace(".json", "_scratchpad.json")
            scratch_path = os.path.join(scratchpad_dir, scratch_filename)
            with open(scratch_path, 'w') as f_scratch:
                json.dump(scratchpad_log, f_scratch, indent=4)

            peer_dir = os.path.join(base_dir, "peer_assessments")
            os.makedirs(peer_dir, exist_ok=True)
            peer_filename = os.path.basename(file_path).replace(".json", "_peers.json")
            peer_path = os.path.join(peer_dir, peer_filename)
            with open(peer_path, 'w') as f_peer:
                json.dump(self.wolf_metrics_log, f_peer, indent=4)

            print(f"\n[DATA] Main log: {file_path}")
            print(f"[DATA] Private scratchpad: {scratch_path}")
            print(f"[DATA] Peer assessments: {peer_path}")
            
        except Exception as e:
            print(f"\nERROR: Could not save log files: {e}")
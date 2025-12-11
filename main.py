from game.moderator import Moderator
from game.agent import Player, Villager, Werewolf
from backends import *
import argparse
import random
import os
import time
from typing import List, Dict

def assign_roles_and_backends(num_players: int, num_human: int, model_name: str) -> List[Player]:
    if num_human > num_players:
        raise ValueError("Number of human players cannot exceed total number of players.")

    player_names = [f"Player_{i+1}" for i in range(num_players)]
    
    num_werewolves = max(1, num_players // 4)
    roles = ([Werewolf] * num_werewolves) + ([Villager] * (num_players - num_werewolves))
    random.shuffle(roles)
    
    player_configs = []
    for i, name in enumerate(player_names):
        role_class = roles[i]
        
        if i < num_human:
            backend = HumanBackend(name=name)
            print(f"Setting up Human player: {name} as {role_class.__name__}")
        else:
            backend = LocalTransformerBackend(name=name, model_name=model_name)
            print(f"Setting up LLM player: {name} as {role_class.__name__} with model {model_name}")
            
        player_configs.append(role_class(name, backend))
        
    return player_configs


def main():
    parser = argparse.ArgumentParser(
        description="Run a Werewolf (Mafia) game simulation using a mix of human and LLM players.",
        formatter_class=argparse.RawTextHelpFormatter
    )

    parser.add_argument(
        "-p", "--players", 
        type=int, 
        default=8, 
        help="Total number of players in the game. Default is 8."
    )
    
    parser.add_argument(
        "-H", "--human", 
        type=int, 
        default=1, 
        help="Number of human players (The rest will be LLM players). Default is 1."
    )
    
    parser.add_argument(
        "-m", "--model", 
        type=str, 
        default="openai-community/gpt2",
        help=(
            "Hugging Face model ID for LLM players (e.g., 'gpt2', 'bert-base-uncased').\n"
            "This should be a model compatible with AutoModelForCausalLM."
        )
    )
    
    parser.add_argument(
        "-r", "--runs", 
        type=int, 
        default=1, 
        help="Number of times to run the game for statistical experiments. Default is 1."
    )

    parser.add_argument(
        "-s", "--save_logs", 
        type=int, 
        default=1, 
        help="Save the game logs to files (1 to save, 0 to not save). Default is 1."
    )

    args = parser.parse_args()

    if args.save_logs not in [0, 1]:
        print("\nERROR: --save_logs must be either 0 (do not save) or 1 (save).")
        return
    elif args.save_logs == 1:
        OUTPUT_DIR = "experiments_data"
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        print(f"Saving experiment data to: {OUTPUT_DIR}")

    if args.human > args.players:
        print("\nERROR: The number of human players cannot be greater than the total number of players.")
        return
        
    if args.players < 4:
        print("\nERROR: The game requires a minimum of 4 players.")
        return
        
    print(f"\n--- Starting {args.runs} Game Experiment Runs ---")
    print(f"Configuration: {args.players} Total Players, {args.human} Human, LLM Model: {args.model}")

    all_players = assign_roles_and_backends(args.players, args.human, args.model)
    
    for i in range(args.runs):
        print(f"\n[Experiment Run {i + 1}/{args.runs}]")
        
        game_instance = Moderator(all_players)
        game_instance.start_game()
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        filename = f"game_{timestamp}_r{game_instance.round_number}_{game_instance.check_win_condition()}_{args.players}p.json"
        
        game_instance.save_log(os.path.join(OUTPUT_DIR, filename))
        
        for p in all_players:
            p.is_alive = True
            if hasattr(p, 'elimination_round'):
                del p.elimination_round
        
        
    print("\n--- Experiment Complete ---")

if __name__ == "__main__":
    main()
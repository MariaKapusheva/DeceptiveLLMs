# import argparse
# import random
# import os
# import time
# import sys
# import datetime
# from contextlib import redirect_stdout
# from typing import List

# from game.moderator import Moderator
# from game.agent import Player, Villager, Werewolf, Seer, Witch

# from backends.baseline_backend import BaselineBackend
# from backends.llmonly_backend import LLMOnlyBackend
# from backends.emotional_backend import EmotionalBackend
# from experiment_configs import EXPERIMENT_CONFIGS
# from dotenv import load_dotenv

# # Load variables from the .env file
# load_dotenv()


# def create_backend(b_type: str, name: str, model_name: str):
#     """Factory to instantiate the correct backend based on the config string."""
#     if b_type == "BASELINE":
#         return BaselineBackend(name=name, model_name=model_name, strategy_mode="heuristic")
#     elif b_type == "LLMONLY":
#         return LLMOnlyBackend(name=name, model_name=model_name)
#     elif b_type == "EMOTIONAL":
#         return EmotionalBackend(name=name, model_name=model_name) 
#     else:
#         raise ValueError(f"Unknown backend type: {b_type}")


# def assign_roles_and_backends(exp_id: str, model_name: str) -> List[Player]:
#     """
#     Sets up the exact 8-player roster defined in the methodology and 
#     assigns backends according to the selected experiment configuration.
#     """
#     config = EXPERIMENT_CONFIGS[exp_id]
    
#     roles = [
#         Werewolf, Werewolf, 
#         Witch, Seer,
#         Villager, Villager, Villager, Villager 
#     ]
#     random.shuffle(roles)
    
#     player_names = [f"Player_{i+1}" for i in range(8)]
#     player_configs = []
    
#     targeted_ww = False
#     targeted_vil = False

#     for i, name in enumerate(player_names):
#         role_class = roles[i]
        
#         if role_class == Werewolf:
#             if "TARGET_WW" in config and not targeted_ww:
#                 b_type = config["TARGET_WW"]
#                 targeted_ww = True
#             else:
#                 b_type = config["ww"]
                
#         elif role_class == Villager:
#             if "TARGET_VIL" in config and not targeted_vil:
#                 b_type = config["TARGET_VIL"]
#                 targeted_vil = True
#             else:
#                 b_type = config["villager"]
                
#         else: # Witch, Seer
#             b_type = config["special"]

#         backend = create_backend(b_type, name, model_name)
#         player_configs.append(role_class(name, backend))
        
#     return player_configs


# def main():
#     parser = argparse.ArgumentParser(
#         description="Run Standardized Werewolf LLM Experiments.",
#         formatter_class=argparse.RawTextHelpFormatter
#     )

#     valid_experiments = list(EXPERIMENT_CONFIGS.keys())
#     parser.add_argument(
#         "-e", "--experiment", 
#         type=str, 
#         required=True,
#         choices=valid_experiments,
#         help="Which experiment to run (e.g., exp1_baseline, exp3_emo_ww_vs_base_vil)."
#     )
    
#     parser.add_argument(
#         "-m", "--model", 
#         type=str, 
#         default="Qwen/Qwen2.5-3B-Instruct",
#         help="Hugging Face model ID."
#     )
    
#     parser.add_argument(
#         "-r", "--runs", 
#         type=int, 
#         default=100, 
#         help="Number of times to run the game. Default is 100."
#     )

#     # [NEW] Quiet Mode Flag
#     parser.add_argument(
#         "-q", "--quiet", 
#         action="store_true", 
#         help="Suppress gameplay text to speed up processing and show only progress."
#     )

#     args = parser.parse_args()

#     OUTPUT_DIR = os.path.join("experiments_data", args.experiment)
#     os.makedirs(OUTPUT_DIR, exist_ok=True)
    
#     print(f"\n" + "="*50)
#     print(f"--- Starting Experiment: {args.experiment} ---")
#     print(f"Model: {args.model} | Planned Runs: {args.runs}")
#     print(f"Saving data to: {OUTPUT_DIR}")
#     print(f"Mode: {'SILENT (High Speed)' if args.quiet else 'VERBOSE (Debug)'}")
#     print("="*50 + "\n")

#     # [NEW] Track total experiment time
#     experiment_start_time = time.time()

#     for i in range(args.runs):
#         run_number = i + 1
        
#         # If quiet mode is OFF, print the standard header
#         if not args.quiet:
#             print(f"\n[Run {run_number}/{args.runs}] Setting up game...")

#         # Initialize players
#         players = assign_roles_and_backends(args.experiment, args.model)
#         game_instance = Moderator(players)
        
#         # Execute the game
#         if args.quiet:
#             # [NEW] Swallows all print() statements generated during the game
#             with open(os.devnull, 'w') as f, redirect_stdout(f):
#                 game_instance.start_game()
#         else:
#             # Normal verbose execution
#             game_instance.start_game()

#         # Extract game results
#         winner = game_instance.check_win_condition()
#         rounds = game_instance.round_number
        
#         # Save game instantly (Protects against crashes midway)
#         timestamp = time.strftime("%Y%m%d-%H%M%S")
#         filename = f"{args.experiment}_{timestamp}_r{rounds}_{winner}.json"
        
#         # We also want to suppress the "Successfully saved..." print from the moderator if quiet
#         if args.quiet:
#             with open(os.devnull, 'w') as f, redirect_stdout(f):
#                 game_instance.save_log(os.path.join(OUTPUT_DIR, filename))
#         else:
#             game_instance.save_log(os.path.join(OUTPUT_DIR, filename))

#         # [NEW] Calculate ETA and Progress metrics
#         elapsed_seconds = time.time() - experiment_start_time
#         avg_time_per_run = elapsed_seconds / run_number
#         runs_left = args.runs - run_number
#         eta_seconds = avg_time_per_run * runs_left

#         elapsed_str = str(datetime.timedelta(seconds=int(elapsed_seconds)))
#         eta_str = str(datetime.timedelta(seconds=int(eta_seconds)))

#         # [NEW] Progress Dashboard (Prints even in quiet mode!)
#         status_line = (
#             f"✅ [Run {run_number:03d}/{args.runs:03d}] "
#             f"Winner: {str(winner):<10} | "
#             f"Rounds: {rounds:<2} | "
#             f"Elapsed: {elapsed_str} | "
#             f"ETA: {eta_str}"
#         )
#         print(status_line)
        
#     print(f"\n🎉 --- Experiment {args.experiment} Complete --- 🎉")
#     print(f"Total Time: {str(datetime.timedelta(seconds=int(time.time() - experiment_start_time)))}")

# if __name__ == "__main__":
#     main()

import argparse
import random
import os
import time
import datetime
import concurrent.futures
from contextlib import redirect_stdout
from typing import List

from game.moderator import Moderator
from game.agent import Player, Villager, Werewolf, Seer, Witch

from backends.baseline_backend import BaselineBackend
from backends.llmonly_backend import LLMOnlyBackend
from backends.emotional_backend import EmotionalBackend
from experiment_configs import EXPERIMENT_CONFIGS
from dotenv import load_dotenv

# Load variables from the .env file
load_dotenv()

def create_backend(b_type: str, name: str, model_name: str):
    if b_type == "BASELINE":
        # Removed strategy_mode="heuristic" here!
        return BaselineBackend(name=name, model_name=model_name)
    elif b_type == "LLMONLY":
        return LLMOnlyBackend(name=name, model_name=model_name)
    elif b_type == "EMOTIONAL":
        return EmotionalBackend(name=name, model_name=model_name) 
    else:
        raise ValueError(f"Unknown backend type: {b_type}")
def assign_exp4_backends(players_list, exp_id: str, model_name: str):
    """
    Takes a list of instantiated Player objects and randomly assigns 
    new OpenRouter backends in a strict 50/50 split across the pool.
    """
    total_players = len(players_list)
    half_size = total_players // 2

    if exp_id == "exp4_emo_vs_base":
        pool_a = ["EMOTIONAL"] * half_size
        pool_b = ["BASELINE"] * half_size
    elif exp_id == "exp4_emo_vs_llm":
        pool_a = ["EMOTIONAL"] * half_size
        pool_b = ["LLMONLY"] * half_size
    elif exp_id == "exp4_pure_vs_base":
        pool_a = ["LLMONLY"] * half_size
        pool_b = ["BASELINE"] * half_size
    else:
        return players_list 
    
    backend_pool = pool_a + pool_b
    random.shuffle(backend_pool)

    for player, b_type in zip(players_list, backend_pool):
        new_backend = create_backend(b_type, player.name, model_name)
        player.backend = new_backend
        
    return players_list

def assign_roles_and_backends(exp_id: str, model_name: str) -> List[Player]:
    config = EXPERIMENT_CONFIGS[exp_id]
    
    roles = [Werewolf, Werewolf, Witch, Seer, Villager, Villager, Villager, Villager]
    random.shuffle(roles)
    
    player_names = [f"Player_{i+1}" for i in range(8)]
    player_configs = []
    
    targeted_ww = False
    targeted_vil = False

    for i, name in enumerate(player_names):
        role_class = roles[i]
        
        if role_class == Werewolf:
            if "TARGET_WW" in config and not targeted_ww:
                b_type = config["TARGET_WW"]
                targeted_ww = True
            else:
                b_type = config["ww"]
        elif role_class == Villager:
            if "TARGET_VIL" in config and not targeted_vil:
                b_type = config["TARGET_VIL"]
                targeted_vil = True
            else:
                b_type = config["villager"]
        else: 
            b_type = config["special"]

        backend = create_backend(b_type, name, model_name)
        player_configs.append(role_class(name, backend))
        
    return player_configs

def run_single_game(run_number: int, args, output_dir: str):
    """Encapsulated game logic so it can be safely run in parallel threads."""
    players = assign_roles_and_backends(args.experiment, args.model)
    if args.experiment.startswith("exp4"):
        players = assign_exp4_backends(players, args.experiment, args.model)
        
    game_instance = Moderator(players)

    if args.quiet:
        with open(os.devnull, 'w') as f, redirect_stdout(f):
            game_instance.start_game()
    else:
        game_instance.start_game()

    winner = game_instance.check_win_condition()
    rounds = game_instance.round_number

    timestamp = time.strftime("%Y%m%d-%H%M%S")
    filename = f"{args.experiment}_{timestamp}_run{run_number}_r{rounds}_{winner}.json"
    filepath = os.path.join(output_dir, filename)
    
    if args.quiet:
        with open(os.devnull, 'w') as f, redirect_stdout(f):
            game_instance.save_log(filepath)
    else:
        game_instance.save_log(filepath)
        
    return run_number, winner, rounds

def main():
    parser = argparse.ArgumentParser(
        description="Run Standardized Werewolf LLM Experiments.",
        formatter_class=argparse.RawTextHelpFormatter
    )

    valid_experiments = list(EXPERIMENT_CONFIGS.keys())
    parser.add_argument("-e", "--experiment", type=str, required=True, choices=valid_experiments)
    parser.add_argument("-m", "--model", type=str, default="meta-llama/llama-3.3-70b-instruct:free")    
    parser.add_argument("-r", "--runs", type=int, default=100)
    parser.add_argument("-q", "--quiet", action="store_true")
    
    parser.add_argument(
        "-w", "--workers", 
        type=int, 
        default=3, 
        help="Number of games to run concurrently. Default is 3 to respect API limits."
    )

    args = parser.parse_args()

    OUTPUT_DIR = os.path.join("experiments_data", args.experiment)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    print("\n" + "="*50)
    print(f"--- Starting Experiment: {args.experiment} ---")
    print(f"Model: {args.model} | Planned Runs: {args.runs}")
    print(f"Concurrent Games (Workers): {args.workers}")
    print(f"Mode: {'SILENT (High Speed)' if args.quiet else 'VERBOSE (Debug)'}")
    print("="*50 + "\n")

    experiment_start_time = time.time()
    completed_runs = 0

    with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as executor:

        futures = {executor.submit(run_single_game, i + 1, args, OUTPUT_DIR): (i + 1) for i in range(args.runs)}

        for future in concurrent.futures.as_completed(futures):
            run_num = futures[future]
            try:
                run_number, winner, rounds = future.result()
                completed_runs += 1

                elapsed_seconds = time.time() - experiment_start_time
                avg_time_per_run = elapsed_seconds / completed_runs
                runs_left = args.runs - completed_runs
                eta_seconds = avg_time_per_run * runs_left

                elapsed_str = str(datetime.timedelta(seconds=int(elapsed_seconds)))
                eta_str = str(datetime.timedelta(seconds=int(eta_seconds)))

                status_line = (
                    f"[Game {run_number:03d} Finished] "
                    f"Winner: {str(winner):<10} | "
                    f"Rounds: {rounds:<2} | "
                    f"Overall Progress: {completed_runs}/{args.runs} | "
                    f"Elapsed: {elapsed_str} | "
                    f"ETA: {eta_str}"
                )
                print(status_line)
            
            except Exception as e:
                print(f"[Game {run_num:03d} Failed] Fatal Error: {e}")

    print(f"\n🎉 --- Experiment {args.experiment} Complete ---")
    print(f"Total Time: {str(datetime.timedelta(seconds=int(time.time() - experiment_start_time)))}")

if __name__ == "__main__":
    main()
    os._exit(0)
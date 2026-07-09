EXPERIMENT_CONFIGS = {
    # Experiment 1
    "exp1_baseline":  {"ww": "BASELINE",  "villager": "BASELINE",  "special": "BASELINE"},
    "exp1_llmonly":   {"ww": "LLMONLY",   "villager": "LLMONLY",   "special": "LLMONLY"},
    "exp1_emotional": {"ww": "EMOTIONAL", "villager": "EMOTIONAL", "special": "EMOTIONAL"},
    
    # Experiment 2
    "exp2_emo_ww_vs_base":  {"TARGET_WW": "EMOTIONAL", "ww": "BASELINE", "villager": "BASELINE", "special": "BASELINE"},
    "exp2_emo_vil_vs_base": {"TARGET_VIL": "EMOTIONAL", "ww": "BASELINE", "villager": "BASELINE", "special": "BASELINE"},
    "exp2_emo_ww_vs_llm":   {"TARGET_WW": "EMOTIONAL", "ww": "LLMONLY",  "villager": "LLMONLY",  "special": "LLMONLY"},
    "exp2_emo"
    ""
    "_vil_vs_llm":  {"TARGET_VIL": "EMOTIONAL", "ww": "LLMONLY",  "villager": "LLMONLY",  "special": "LLMONLY"},

    # Experiment 3
    "exp3_emo_ww_vs_base_vil": {"ww": "EMOTIONAL", "villager": "BASELINE",  "special": "BASELINE"},
    "exp3_emo_vil_vs_base_ww": {"ww": "BASELINE",  "villager": "EMOTIONAL", "special": "EMOTIONAL"},
    "exp3_emo_ww_vs_llm_vil":  {"ww": "EMOTIONAL", "villager": "LLMONLY",   "special": "LLMONLY"},
    "exp3_emo_vil_vs_llm_ww":  {"ww": "LLMONLY",   "villager": "EMOTIONAL", "special": "EMOTIONAL"},
    "exp3_llm_ww_vs_base_vil": {"ww": "LLMONLY",   "villager": "BASELINE",  "special": "BASELINE"},
    "exp3_base_ww_vs_llm_vil": {"ww": "BASELINE", "villager": "LLMONLY", "special": "LLMONLY"},

    # Experiment 4
    "exp4_emo_vs_base": {
        "ww": "BASELINE",
        "villager": "BASELINE",
        "special": "BASELINE"
    },
    "exp4_emo_vs_llm": {
        "ww": "BASELINE",
        "villager": "BASELINE",
        "special": "BASELINE"
    },
    "exp4_pure_vs_base": {
        "ww": "BASELINE",
        "villager": "BASELINE",
        "special": "BASELINE"
    }
}
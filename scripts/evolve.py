"""
Genetic Prompt Evolution (The "Mad Scientist" Engine)

This script uses an evolutionary algorithm to discover the mathematically optimal Text-to-Video 
prompt structure for Wan. It runs LIVE on DashScope, burning real API quota to evolve prompts, 
rendering real videos, scoring them with real Qwen-VL, and persisting the lineage to prove 
the empirical rigor of the system without any mocks.
"""

import argparse
import json
import time
from pathlib import Path

from auteur.agents.cinematographer import Cinematographer
from auteur.config import BudgetConfig, Tier
from auteur.budget import BudgetGovernor
from auteur.llm import QwenClient
from bench.rubric import RUBRIC_SYS

_SYS_MUTATE = """You are an evolutionary algorithm designer optimizing text-to-video prompt strategies.
Given a successful prompt strategy and its Qwen-VL judge score, mutate it to create a NEW, distinct strategy.
Change the focus—maybe prioritize lighting over camera movement, or emotion over action. 
Return ONLY JSON: {"strategy_name": "...", "system_prompt_instruction": "..."}"""

_INITIAL_POPULATION = [
    {
        "strategy_name": "Cinematography First",
        "system_prompt_instruction": "Focus entirely on camera angles, lens mm, lighting direction, and film stock. Describe the visual geometry."
    },
    {
        "strategy_name": "Subject Emotion First",
        "system_prompt_instruction": "Focus intensely on the subject's micro-expressions, posture, eye movement, and internal emotional state. Minimal environmental details."
    },
    {
        "strategy_name": "Minimalist Action",
        "system_prompt_instruction": "Use sharp, stark verbs. Describe exactly one clear, continuous physical action. No flowery adjectives."
    }
]

def run_evolution(generations: int, population_size: int, premise: str, outdir: Path):
    outdir.mkdir(parents=True, exist_ok=True)
    
    # We use a massive budget because this is an experimental harness, but it spends real money!
    ledger_path = outdir / "evolution_budget.json"
    if ledger_path.exists():
        ledger_path.unlink()
    gov = BudgetGovernor(BudgetConfig(max_spend_usd=50.0), ledger_path=ledger_path)
    client = QwenClient(gov)
    dp = Cinematographer(gov, resolution="480P") # Keep resolution low to save time/money
    
    population = _INITIAL_POPULATION[:population_size]
    ledger = []

    print(f"Starting Genetic Evolution (Generations: {generations}, Population: {population_size})")
    
    for gen in range(generations):
        print(f"\n--- Generation {gen + 1} ---")
        gen_results = []
        
        for idx, individual in enumerate(population):
            strat_name = individual["strategy_name"]
            instruction = individual["system_prompt_instruction"]
            print(f"\nIndividual {idx + 1}: {strat_name}")
            
            # 1. Generate the Prompt using this Strategy
            prompt_data = client.chat_json(
                "evolver", Tier.CREATIVE,
                [
                    {"role": "system", "content": f"You are a video prompt engineer. {instruction}. Return JSON: {{\"video_prompt\": \"...\"}}"},
                    {"role": "user", "content": f"Write a 1-shot video prompt for this premise: {premise}"}
                ]
            )
            video_prompt = prompt_data.get("video_prompt", premise)
            print(f"   Prompt: {video_prompt[:80]}...")
            
            # 2. Render the Video (REAL Wan call)
            clip_name = f"gen{gen}_ind{idx}.mp4"
            clip_path = outdir / clip_name
            try:
                dp.render(video_prompt, clip_path, duration=3.0)
                print(f"   Rendered -> {clip_name}")
            except Exception as e:
                print(f"   Render FAILED: {e}")
                gen_results.append({"individual": individual, "prompt": video_prompt, "score": 0.0, "error": str(e)})
                continue
                
            # 3. Score the Video (REAL Qwen-VL call)
            try:
                from auteur.agents.editor import Editor
                editor = Editor(client, gov)
                frames = editor.sample_frames(clip_path, n=3)
                content = [{"type": "text", "text": "Judge this shot per the rubric."}]
                content += [{"type": "image_url", "image_url": {"url": u}} for u in frames]
                result = client.vision("rubric_judge", [{"role": "system", "content": RUBRIC_SYS}, {"role": "user", "content": content}])
                score = float(result.get("overall", 0.0)) if isinstance(result, dict) else 0.0
                print(f"   Score: {score}/10")
            except Exception as e:
                print(f"   Score FAILED: {e}")
                score = 0.0
                
            gen_results.append({
                "individual": individual,
                "prompt": video_prompt,
                "clip": clip_name,
                "score": score
            })
            
        ledger.append({"generation": gen + 1, "results": gen_results})
        
        # 4. Selection & Mutation (Evolution)
        if gen < generations - 1:
            gen_results.sort(key=lambda x: x["score"], reverse=True)
            winner = gen_results[0]["individual"]
            winner_score = gen_results[0]["score"]
            print(f"\nGeneration {gen + 1} Winner: {winner['strategy_name']} (Score: {winner_score})")
            
            next_population = [winner] # Elitism: keep the winner
            
            attempts = 0
            while len(next_population) < population_size and attempts < 3:
                attempts += 1
                try:
                    mutant = client.chat_json(
                        "evolver", Tier.CREATIVE,
                        [
                            {"role": "system", "content": _SYS_MUTATE},
                            {"role": "user", "content": f"Winning strategy: {winner['strategy_name']}\nInstruction: {winner['system_prompt_instruction']}\nScore: {winner_score}/10. Mutate it."}
                        ]
                    )
                    if "strategy_name" in mutant and "system_prompt_instruction" in mutant:
                        next_population.append(mutant)
                        print(f"   Mutated new strategy: {mutant['strategy_name']}")
                    else:
                        print("   Mutation missing keys, using fallback...")
                        next_population.append(winner)
                except Exception as e:
                    print(f"   Mutation failed: {e}")
                    next_population.append(winner) # Fallback
            population = next_population

    # 5. Persist Ledger
    ledger_path = outdir / "evolution_ledger.json"
    ledger_path.write_text(json.dumps(ledger, indent=2), encoding="utf-8")
    print(f"\nEvolution complete! Lineage saved to {ledger_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--generations", type=int, default=2)
    parser.add_argument("--population", type=int, default=2)
    parser.add_argument("--premise", type=str, default="A woman staring out a rainy window, cinematic lighting.")
    args = parser.parse_args()
    
    import os
    if os.getenv("AUTEUR_MOCK", "").lower() in {"1", "true", "yes"}:
        print("\nWARNING: Running in MOCK mode. The evolutionary engine is using fake video generation")
        print("and deterministic critic scoring. To evolve real mathematically optimal prompts,")
        print("run without AUTEUR_MOCK=1 and provide a DASHSCOPE_API_KEY.\n")
    else:
        print("\nMAD SCIENTIST MODE ACTIVATED. Burning real tokens to discover the truth.\n")
        # Ensure we actually crash if no key is present in live mode
        from auteur.config import require_api_key
        try:
            require_api_key()
        except Exception as e:
            print(f"Cannot run live evolution: {e}")
            print("Falling back to MOCK mode for safety...")
            os.environ["AUTEUR_MOCK"] = "1"
    
    run_evolution(args.generations, args.population, args.premise, Path("out_evolution"))

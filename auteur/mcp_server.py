"""Model Context Protocol (MCP) Server for Auteur.

Exposes Auteur's core production, budget, and critic capabilities as standardized MCP tools.
External agents (e.g., Claude, Cursor, Qwen Studio) can connect to this server and use these tools
to build or critique AI video productions autonomously.
"""

from typing import Dict, Any, List
import json
from pathlib import Path
from mcp.server.fastmcp import FastMCP

from auteur.config import ProductionConfig
from auteur.agents.showrunner import Showrunner
from auteur.agents.editor import Editor
from auteur.llm import QwenClient
from auteur.budget import BudgetGovernor

# Initialize the MCP Server
mcp = FastMCP("auteur")


@mcp.tool()
def auteur_produce(
    premise: str,
    episodes: int = 1,
    shots_per_episode: int = 4,
    mock: bool = True
) -> str:
    """Produce a full AI short film or series from a premise.
    
    Args:
        premise: The story idea or logline.
        episodes: Number of episodes to produce (Series Mode).
        shots_per_episode: Number of shots in each episode script.
        mock: If true, use AUTEUR_MOCK mode (no API charges).
        
    Returns:
        JSON string describing the final manifest and paths to deliverables.
    """
    import os
    if mock:
        os.environ["AUTEUR_MOCK"] = "1"
        
    out_dir = Path("series_out" if episodes > 1 else "out")
    
    # We invoke the series runner logic for simplicity
    from auteur.series import run_series
    run_series(
        premise=premise,
        episodes=episodes,
        shots_per_episode=shots_per_episode,
        out_dir=out_dir
    )
    
    manifest_path = out_dir / ("series_manifest.json" if episodes > 1 else "manifest.json")
    if manifest_path.exists():
        return f"Production successful. Manifest at {manifest_path.resolve()}"
    return "Production completed but manifest not found."


@mcp.tool()
def auteur_budget(workdir: str = "out") -> str:
    """Check the token and spend ledger for a production.
    
    Args:
        workdir: Directory of the production (e.g., 'out').
        
    Returns:
        A formatted JSON string of the budget summary (tokens used, clips rendered, retakes, USD spend).
    """
    ledger_path = Path(workdir) / "ledger.json"
    if not ledger_path.exists():
        return json.dumps({"error": f"No ledger found at {ledger_path.resolve()}"})
        
    cfg = ProductionConfig()
    governor = BudgetGovernor(cfg.budget, ledger_path=ledger_path)
    return json.dumps(governor.summary(), indent=2)


@mcp.tool()
def auteur_critique(video_path: str, prompt_text: str = "", workdir: str = "out") -> str:
    """Run the Auteur Qwen-VL Critic on a given video file.
    
    Evaluates the video on 4 axes: overall cinematic quality, prompt adherence, character consistency, and continuity.
    
    Args:
        video_path: Absolute path to the .mp4 file.
        prompt_text: What the video is supposed to depict.
        workdir: Working directory to extract frames into.
        
    Returns:
        JSON string containing the critic's scores and rationale.
    """
    from auteur.models import Shot
    from auteur import media
    
    path = Path(video_path)
    if not path.exists():
        return json.dumps({"error": f"Video not found: {path}"})
        
    cfg = ProductionConfig()
    governor = BudgetGovernor(cfg.budget, ledger_path=Path(workdir) / "ledger.json")
    client = QwenClient(governor)
    editor = Editor(client, governor)
    
    # Dummy shot for the critic to evaluate
    shot = Shot(index=0, beat_index=0, description=prompt_text, video_prompt=prompt_text, dialogue="")
    
    try:
        frames = media.extract_frames(path)
        review = editor.critique(shot, frames, prev_frame_uris=None)
        return json.dumps(review, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


if __name__ == "__main__":
    mcp.run()

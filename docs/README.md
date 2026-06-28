# Auteur Documentation

Welcome to the documentation for Auteur, the Budget-Aware AI Showrunner. 

This directory contains deep-dives into the architecture, design decisions, and system constraints.

## Table of Contents
- [Architecture & Build Roadmap](ARCHITECTURE.md): The full system diagram, module map, and design principles, including the token economy and 4-axis critic loop.

## Design Tradeoffs & Constraints

Auteur treats video generation like a real production, which means it introduces deliberate tradeoffs to optimize for token cost and quality.

### LLM-as-a-Judge
The evaluation harness (`bench/`) uses Qwen-VL to score the outputs produced by Qwen-Max and Wan. While this introduces an element of self-grading (the Qwen ecosystem judging its own outputs), it's a deliberate design choice: we are using the multimodal intelligence of the Qwen ecosystem to orchestrate *itself* in a closed feedback loop. The Qwen-VL model acts as an impartial visual continuity editor that replaces a human director.

### Speed vs. Continuity (The Director's Choice)
Auteur supports a `--no-consistency` flag. 
- **Sequential Rendering (Default)**: Uses Image-to-Video (i2v) to chain the final frame of the previous shot into the next. This ensures character and visual continuity (faces stay the same) but requires rendering one shot at a time.
- **Parallel Rendering (`--no-consistency`)**: Renders all shots concurrently via a thread pool for a massive wall-clock speedup. However, this relies entirely on Text-to-Video (t2v), sacrificing cross-shot continuity. 

### Audio & FFmpeg Constraints
The system uses a highly optimized but static procedural audio bed. It chooses a single mood for the entire video (or climax beat) and synthesizes a basic triad pad mixed under the TTS dialogue. Final assembly relies on the local system's `ffmpeg` implementation (which can have specific codec quirks on Windows). Ensure your environment has a stable `ffmpeg` installed.

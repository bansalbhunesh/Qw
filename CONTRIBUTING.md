# Contributing to Auteur

Thank you for considering contributing to **Auteur — The Budget-Aware AI Showrunner**! Whether you're fixing a bug, adding a feature, or improving documentation, your contribution is welcome.

---

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Project Structure](#project-structure)
- [Making Changes](#making-changes)
- [Testing](#testing)
- [Coding Standards](#coding-standards)
- [Pull Request Process](#pull-request-process)
- [Reporting Issues](#reporting-issues)

---

## Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](https://www.contributor-covenant.org/version/2/1/code_of_conduct/). By participating, you agree to uphold a welcoming, inclusive, and harassment-free environment.

---

## Getting Started

1. **Fork** the repository on GitHub.
2. **Clone** your fork locally:
   ```bash
   git clone https://github.com/<your-username>/Qw.git
   cd Qw
   ```
3. **Create a branch** for your work:
   ```bash
   git checkout -b feat/your-feature-name
   ```

---

## Development Setup

### Prerequisites

- **Python 3.11+**
- **ffmpeg** installed and available on `PATH` (or let `imageio-ffmpeg` provide a static fallback)
- A virtual environment is strongly recommended

### Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Environment configuration

```bash
cp .env.example .env
```

For local development, **no API key is needed** — the project runs fully in mock mode when `AUTEUR_MOCK=1` or when no `DASHSCOPE_API_KEY` is set.

### Verify your setup

```bash
# Run the test suite (mock mode, no API calls)
AUTEUR_MOCK=1 python -m pytest -q

# Run a full mock production
AUTEUR_MOCK=1 python -m auteur.cli "A lighthouse keeper teaches the drone sent to replace him"
```

---

## Project Structure

```
auteur/                     # Core package
├── agents/                 # AI agent modules (Writer, Art Director, Cinematographer, etc.)
│   ├── writer.py           # Premise → beat sheet → script
│   ├── art_director.py     # Character & Style Bible generation
│   ├── cinematographer.py  # Wan video rendering (t2v / i2v)
│   ├── editor.py           # Qwen-VL critic loop + assembly
│   ├── sound.py            # CosyVoice TTS + procedural score
│   ├── prompt_optimizer.py # Wan-specific prompt refinement
│   └── showrunner.py       # Orchestrator — the budgeted control loop
├── budget.py               # Budget Governor — token metering & spend caps
├── config.py               # Model IDs, endpoints, tier maps
├── llm.py                  # Metered Qwen client with tiered routing
├── transport.py            # Pluggable LLM transport (live vs. mock)
├── media.py                # ffmpeg operations (clips, frames, assembly)
├── models.py               # Data structures (Beat, Shot, Script, etc.)
├── series.py               # Multi-episode series mode
├── storyboard.py           # HTML storyboard export
├── viewer.py               # Live web Studio (SSE streaming)
├── cli.py                  # CLI entrypoint
└── ...
bench/                      # Benchmark & ablation harness
deploy/                     # Alibaba Cloud deployment (ECS + OSS)
docs/                       # Architecture docs & diagrams
scripts/                    # Utilities (diagnostics, reel generator, probes)
tests/                      # Test suite (85+ tests)
```

---

## Making Changes

### Branch naming

Use descriptive, prefixed branch names:

| Prefix     | Use case                          |
|------------|-----------------------------------|
| `feat/`    | New feature                       |
| `fix/`     | Bug fix                           |
| `docs/`    | Documentation only                |
| `refactor/`| Code restructuring (no behavior change) |
| `test/`    | Adding or updating tests          |
| `chore/`   | Build, CI, tooling changes        |

### Commit messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat(budget): add per-tier spend breakdown to ledger
fix(critic): handle empty frame list in cross-shot continuity
docs: update ARCHITECTURE.md with series mode flow
test(sound): add CosyVoice fallback voice tests
```

---

## Testing

All contributions **must** pass the existing test suite and include tests for new functionality.

```bash
# Run the full suite
AUTEUR_MOCK=1 python -m pytest -q

# Run a specific test file
AUTEUR_MOCK=1 python -m pytest tests/test_budget.py -v

# Run the benchmark (validates harness mechanics)
AUTEUR_MOCK=1 python -m bench.benchmark --premises bench/premises.txt

# Run the ablation study
AUTEUR_MOCK=1 python -m bench.ablation --premise "A lighthouse keeper teaches the drone sent to replace him"
```

### Test guidelines

- All tests run in **mock mode** (`AUTEUR_MOCK=1`) — no API keys or network calls required.
- Use `MockTransport` (from `auteur/transport.py`) for any new LLM-dependent tests.
- Keep tests deterministic and fast.
- Place test files in `tests/` and name them `test_<module>.py`.

---

## Coding Standards

### Python style

- **PEP 8** with a 100-character line length.
- Use **type hints** for function signatures.
- Prefer **f-strings** over `.format()` or `%`-formatting.
- Use **pathlib.Path** for file system operations where practical.

### Architecture principles

- **Budget-aware by default.** Every LLM call must go through the metered client (`auteur/llm.py`) with an appropriate tier (`grunt`, `creative`, `vision`).
- **Mock-safe.** New features must work in mock mode without API keys. Use the `MockTransport` seam.
- **Fail gracefully.** Individual agent failures should never crash the production. Log, skip, and ship what works.
- **Ledger everything.** If it costs tokens, it must appear in the token ledger.

### Documentation

- Add docstrings to all public functions and classes.
- Update `docs/ARCHITECTURE.md` if your change affects the module map or control flow.
- Update `README.md` if your change adds user-facing features or CLI flags.

---

## Pull Request Process

1. **Ensure all tests pass** before submitting.
2. **Update documentation** (README, ARCHITECTURE.md) if applicable.
3. **Fill out the PR template** with:
   - A clear description of *what* and *why*
   - Screenshots or terminal output for visual/behavioral changes
   - Link to any related issues
4. **Keep PRs focused** — one feature or fix per PR.
5. PRs require at least **one approving review** before merge.
6. Squash commits on merge for a clean history.

---

## Reporting Issues

When filing an issue, please include:

- **Environment**: Python version, OS, ffmpeg version
- **Steps to reproduce**: Minimal commands to trigger the issue
- **Expected vs. actual behavior**
- **Logs**: Relevant terminal output or error tracebacks
- **Mock or live?**: Whether the issue occurs in mock mode or with a real API key

### Issue labels

| Label          | Meaning                           |
|----------------|-----------------------------------|
| `bug`          | Something isn't working           |
| `enhancement`  | New feature or improvement        |
| `documentation`| Docs need updating                |
| `good first issue` | Beginner-friendly tasks       |
| `help wanted`  | Community contributions welcome   |

---

## Questions?

If you're unsure about anything, open a [Discussion](https://github.com/bansalbhunesh/Qw/discussions) or file an issue tagged `question`. We're happy to help!

---

Thank you for helping make Auteur better. 🎬

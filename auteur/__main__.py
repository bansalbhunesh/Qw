"""Allow `python -m auteur ...` as an alias for `python -m auteur.cli ...`."""

from .cli import main

raise SystemExit(main())

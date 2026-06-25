"""Allow `python -m bench ...` as an alias for `python -m bench.benchmark ...`."""

from .benchmark import main

raise SystemExit(main())

#!/usr/bin/env python3
"""Compatibility CLI for the repo-scoped Amazon Listing Doctor skill."""

from __future__ import annotations

import runpy
from pathlib import Path
from typing import Any


CORE = (
    Path(__file__).resolve().parents[1]
    / ".agents"
    / "skills"
    / "amazon-listing-doctor"
    / "scripts"
    / "diagnose_listing.py"
)
NAMESPACE: dict[str, Any] = runpy.run_path(str(CORE))
diagnose = NAMESPACE["diagnose"]
main = NAMESPACE["main"]


if __name__ == "__main__":
    raise SystemExit(main())

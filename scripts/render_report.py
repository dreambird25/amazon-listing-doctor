#!/usr/bin/env python3
"""Compatibility CLI for localized Amazon Listing Doctor reports."""

from __future__ import annotations

import runpy
from pathlib import Path


CORE = (
    Path(__file__).resolve().parents[1]
    / ".agents"
    / "skills"
    / "amazon-listing-doctor"
    / "scripts"
    / "render_report.py"
)
main = runpy.run_path(str(CORE))["main"]


if __name__ == "__main__":
    raise SystemExit(main())

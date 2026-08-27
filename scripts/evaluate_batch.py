#!/usr/bin/env python3
"""Compatibility CLI for private Golden Dataset evaluation."""

from __future__ import annotations

import runpy
import sys
from pathlib import Path


SCRIPT_DIR = (
    Path(__file__).resolve().parents[1]
    / ".agents"
    / "skills"
    / "amazon-listing-doctor"
    / "scripts"
)
sys.path.insert(0, str(SCRIPT_DIR))
main = runpy.run_path(str(SCRIPT_DIR / "evaluate_batch.py"))["main"]


if __name__ == "__main__":
    raise SystemExit(main())

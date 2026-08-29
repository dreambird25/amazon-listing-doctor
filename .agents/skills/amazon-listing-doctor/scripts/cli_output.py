#!/usr/bin/env python3
"""Write CLI artifacts with an explicit UTF-8 boundary."""

from __future__ import annotations

from pathlib import Path


def emit_utf8(text: str, output: Path | None = None) -> None:
    """Print to stdout or write one UTF-8 artifact when an output path is supplied."""
    if output is None:
        print(text)
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text.rstrip("\n") + "\n", encoding="utf-8")

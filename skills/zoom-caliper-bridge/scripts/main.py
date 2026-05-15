#!/usr/bin/env python3
"""Run the shared Caliper bridge tool from the individual skill folder."""

from pathlib import Path
import runpy


ROOT_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "caliper_bridge.py"


if __name__ == "__main__":
    runpy.run_path(str(ROOT_SCRIPT), run_name="__main__")

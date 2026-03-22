"""Copilot CLI integration: runs AI-powered analysis via subprocess."""

import subprocess
import time
from datetime import datetime

from .config import COPILOT_BIN


def run_copilot_analysis(prompt: str, model: str) -> str:
    """
    Call the Copilot CLI in non-interactive (--prompt) mode and return the
    full text response.
    """
    t_start = time.monotonic()
    start_ts = datetime.now().strftime("%H:%M:%S")
    print(f"  [copilot] Start     : {start_ts}")
    print(f"  [copilot] Model     : {model}")
    try:
        result = subprocess.run(
            [
                COPILOT_BIN,
                "--model", model,
                "--prompt", prompt,
                "--deny-tool=write",   # prevent any accidental file edits
            ],
            capture_output=True,
            text=True,
            timeout=600,   # 10 min — Opus on long prompts can be slow
        )
        elapsed = time.monotonic() - t_start
        end_ts = datetime.now().strftime("%H:%M:%S")
        print(f"  [copilot] End       : {end_ts}")
        print(f"  [copilot] Time taken: {elapsed:.1f}s")
        output = result.stdout.strip()
        if result.returncode != 0 and not output:
            err = result.stderr.strip()
            return f"[Copilot CLI error (exit {result.returncode}): {err}]"
        # output = "abc"
        return output
    except FileNotFoundError:
        return f"[Copilot CLI not found at '{COPILOT_BIN}'. Check the COPILOT_BIN path.]"
    except subprocess.TimeoutExpired:
        elapsed = time.monotonic() - t_start
        print(f"  [copilot] Timed out after {elapsed:.1f}s")
        return "[Copilot CLI timed out after 10 minutes.]"

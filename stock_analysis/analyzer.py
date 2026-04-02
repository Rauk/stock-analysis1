"""Copilot CLI integration: runs AI-powered analysis via subprocess."""

import subprocess
import time
from datetime import datetime

from .config import COPILOT_BIN

DEFAULT_TIMEOUT_SECONDS = 1800  # 30 minutes


def run_copilot_analysis(prompt: str, model: str, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> str:
    """
    Call the Copilot CLI in non-interactive (--prompt) mode and return the
    full text response.

    Args:
        prompt:  The analysis prompt to send to the model.
        model:   Model ID string (e.g. 'claude-sonnet-4-5').
        timeout: Max seconds to wait before giving up (default: 1800 / 30 min).
                 If the process times out but produced partial output, that
                 partial output is returned with a warning banner appended.
    """
    t_start = time.monotonic()
    start_ts = datetime.now().strftime("%H:%M:%S")
    print(f"  [copilot] Start     : {start_ts}")
    print(f"  [copilot] Model     : {model}")
    print(f"  [copilot] Timeout   : {timeout // 60}m {timeout % 60:02d}s")

    try:
        proc = subprocess.Popen(
            [
                COPILOT_BIN,
                "--model", model,
                "--prompt", prompt,
                "--deny-tool=write",   # prevent any accidental file edits
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
            elapsed = time.monotonic() - t_start
            end_ts = datetime.now().strftime("%H:%M:%S")
            print(f"  [copilot] End       : {end_ts}")
            print(f"  [copilot] Time taken: {elapsed:.1f}s")
            output = stdout.strip()
            if proc.returncode != 0 and not output:
                err = stderr.strip()
                return f"[Copilot CLI error (exit {proc.returncode}): {err}]"
            return output

        except subprocess.TimeoutExpired:
            proc.kill()
            partial_stdout, _ = proc.communicate()
            elapsed = time.monotonic() - t_start
            mins = int(elapsed // 60)
            print(f"  [copilot] Timed out after {elapsed:.1f}s — process killed")

            partial = (partial_stdout or "").strip()
            warning = (
                f"\n\n---\n\n"
                f"> ⚠️ **Analysis timed out after {mins} minutes.** "
                f"The report above may be incomplete. "
                f"Re-run with a longer `--timeout` value or use `--model sonnet` for faster results."
            )
            if partial:
                print(f"  [copilot] Partial output recovered: {len(partial)} chars")
                return partial + warning
            return f"[Copilot CLI timed out after {mins} minutes. No output was produced.]{warning}"

    except FileNotFoundError:
        return f"[Copilot CLI not found at '{COPILOT_BIN}'. Check the COPILOT_BIN path.]"

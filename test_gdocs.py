#!/usr/bin/env python3
"""
Google Docs connectivity test.

Creates or updates a Google Doc with a timestamp + random text,
without running any stock analysis. Use this to verify that your
service account credentials, Google Docs API, and Google Drive API
are all working correctly before running the full stock analysis.

Usage:
    python3 test_gdocs.py --symbol INFY
    python3 test_gdocs.py --symbol INFY --folder-id 1ABC123xyz
"""

import argparse
import os
import random
import string
import sys
from datetime import datetime


def random_text(n: int = 80) -> str:
    words = [
        "alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "golf",
        "hotel", "india", "juliet", "kilo", "lima", "mike", "november",
        "oscar", "papa", "quebec", "romeo", "sierra", "tango", "uniform",
        "victor", "whiskey", "xray", "yankee", "zulu",
    ]
    return " ".join(random.choices(words, k=12))


def main():
    parser = argparse.ArgumentParser(
        description="Test Google Docs create/update without running stock analysis."
    )
    parser.add_argument(
        "--symbol", required=True,
        help="Stock symbol to use as the doc name (e.g. INFY). "
             "Doc will be named 'Stock Analysis - SYMBOL'.",
    )
    parser.add_argument(
        "--folder-id", default=None,
        help="Google Drive folder ID to create the doc in. "
             "Overrides GOOGLE_DRIVE_FOLDER_ID env var.",
    )
    args = parser.parse_args()

    # Allow --folder-id to override env var
    if args.folder_id:
        os.environ["GOOGLE_DRIVE_FOLDER_ID"] = args.folder_id

    # Check required env var
    if not os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip():
        print("\n❌  GOOGLE_SERVICE_ACCOUNT_JSON is not set.")
        print('   export GOOGLE_SERVICE_ACCOUNT_JSON="/path/to/service-account.json"')
        sys.exit(1)

    # Lazy import so missing packages give a clear message
    try:
        from stock_analysis.google_docs import get_or_create_doc, prepend_analysis_to_doc
    except ImportError as e:
        print(f"\n❌  Google API packages not installed: {e}")
        print("   Run: pip install google-api-python-client google-auth")
        sys.exit(1)

    symbol      = args.symbol.upper()
    now         = datetime.now()
    report_date = now.strftime("%d %B %Y")
    timestamp   = now.strftime("%Y-%m-%d %H:%M:%S")
    test_body   = random_text()
    folder_id   = os.environ.get("GOOGLE_DRIVE_FOLDER_ID", "").strip() or None

    print("\n" + "═" * 56)
    print(f"  Google Docs connectivity test")
    print(f"  Symbol    : {symbol}")
    print(f"  Timestamp : {timestamp}")
    print(f"  Folder ID : {folder_id or '(not set — service account Drive)'}")
    print("═" * 56)

    test_content = (
        f"# [TEST] Stock Analysis - {symbol}\n\n"
        f"| | |\n|---|---|\n"
        f"| **Timestamp** | {timestamp} |\n"
        f"| **Symbol**    | {symbol} |\n"
        f"| **Test text** | {test_body} |\n\n"
        f"This entry was written by the Google Docs connectivity test script.\n"
    )

    print("\n[1/2] Getting or creating doc …")
    try:
        doc_id, doc_url = get_or_create_doc(symbol, symbol)
    except Exception as e:
        print(f"\n❌  Failed to get/create doc:\n{e}")
        sys.exit(1)

    print(f"\n[2/2] Prepending test content …")
    try:
        prepend_analysis_to_doc(doc_id, test_content, report_date)
    except Exception as e:
        print(f"\n❌  Failed to write to doc:\n{e}")
        sys.exit(1)

    print("\n" + "═" * 56)
    print(f"  ✓  Test passed!")
    print(f"  Doc URL : {doc_url}")
    print("═" * 56 + "\n")


if __name__ == "__main__":
    main()

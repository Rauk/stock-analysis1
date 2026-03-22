"""CLI entry point: argument parsing and main orchestration."""

import argparse
import re
import smtplib
import sys
import textwrap
import time
from datetime import datetime

from .analyzer import run_copilot_analysis
from .config import COPILOT_MODELS, EMAIL_CONFIG, ANALYSIS_PROMPT_TEMPLATE
from .email_sender import report_to_html, send_email
from .scraper import scrape_groww, scrape_screener, format_screener_report


def parse_args():
    parser = argparse.ArgumentParser(
        description="AI-powered Indian stock analysis — primary source: BSE/NSE India",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples (large-cap — name & symbol known):
              python3 main.py \\
                --name "Infosys" --symbol "INFY" \\
                --screener "https://www.screener.in/company/INFY/" \\
                --groww "https://groww.in/stocks/infosys-ltd"

            Examples (micro/small-cap — let the tool auto-detect name & symbol):
              python3 main.py \\
                --screener "https://www.screener.in/company/CELLECOR/" \\
                --groww "https://groww.in/stocks/cellecor-gadgets-ltd"

              python3 main.py \\
                --screener "https://www.screener.in/company/CELLECOR/"

            Override model:
              python3 main.py --screener "..." --model opus
        """),
    )
    parser.add_argument("--name",     default=None, help="Company name — auto-detected from Screener if omitted")
    parser.add_argument("--symbol",   default=None, help="NSE/BSE ticker — auto-detected from Screener URL if omitted")
    parser.add_argument("--screener", required=True, help="Screener.in company URL (used for auto-detection + reference)")
    parser.add_argument("--groww",    default=None, help="Groww stock URL (optional supplementary reference)")
    parser.add_argument(
        "--model",
        choices=["sonnet", "opus"],
        default="sonnet",
        help="Claude model: 'sonnet' (default, faster) | 'opus' (more thorough)",
    )
    parser.add_argument(
        "--no-email",
        action="store_true",
        help="Skip sending email — print to console only (email is on by default)",
    )
    parser.add_argument(
        "--save",
        metavar="FILE",
        help="Save the report to a file",
    )
    return parser.parse_args()


def to_bse_slug(company_name: str) -> str:
    """Convert company name to a BSE URL slug (lowercase, hyphens)."""
    return re.sub(r"[^a-z0-9]+", "-", company_name.lower()).strip("-")


def _print_timing_summary(script_start: float) -> None:
    total = time.monotonic() - script_start
    end_ts = datetime.now().strftime("%H:%M:%S")
    mins, secs = divmod(int(total), 60)
    print(f"\n{'='*60}")
    print(f"  Finished at  : {end_ts}")
    print(f"  Total time   : {mins}m {secs}s  ({total:.1f}s)")
    print(f"{'='*60}\n")


def main():
    args = parse_args()
    model_id    = COPILOT_MODELS[args.model]
    report_date = datetime.now().strftime("%d %B %Y")

    script_start    = time.monotonic()
    script_start_ts = datetime.now().strftime("%H:%M:%S")

    # 1. Scrape Screener.in — also auto-detects company metadata
    print(f"\n{'='*60}")
    print(f"  Model          : {model_id}")
    print(f"  Date           : {report_date}")
    print(f"  Started at     : {script_start_ts}")
    print(f"{'='*60}\n")

    print("[1/3] Fetching supplementary data …")
    metadata, screener_data, screener_context = scrape_screener(args.screener)

    # Fill in name/symbol from metadata if not supplied by user
    company_name = args.name or metadata.name
    stock_symbol = args.symbol or metadata.symbol

    if not company_name or not stock_symbol:
        print("\n  [ERROR] Could not determine company name or symbol.")
        print("  Screener.in page may be behind a login wall or the URL is incorrect.")
        print("  Pass --name and --symbol explicitly to proceed.\n")
        sys.exit(1)

    # Report what was auto-detected
    if not args.name or not args.symbol:
        detected = []
        if not args.name:
            detected.append(f"name='{company_name}'")
        if not args.symbol:
            detected.append(f"symbol='{stock_symbol}'")
        print(f"  [auto-detected] {', '.join(detected)}")
        if metadata.bse_code:
            print(f"  [auto-detected] bse_code='{metadata.bse_code}'")
        if metadata.nse_symbol:
            print(f"  [auto-detected] nse_symbol='{metadata.nse_symbol}'")

    bse_slug   = to_bse_slug(company_name)
    bse_code   = metadata.bse_code   or stock_symbol   # fallback: use symbol
    nse_symbol = metadata.nse_symbol or stock_symbol

    print(f"\n  Stock Analysis : {company_name} ({stock_symbol})")
    print(f"  BSE Code       : {bse_code or 'unknown'}")

    # Scrape Groww if URL was provided
    if args.groww:
        groww_data    = scrape_groww(args.groww)
        groww_section = f"Groww       : {args.groww}"
        groww_data_section = f"### Pre-fetched from Groww (unverified reference)\n{groww_data}"
    else:
        groww_data         = ""
        groww_section      = "Groww       : [not provided]"
        groww_data_section = ""

    # 2. Build prompt and run AI analysis
    print("\n[2/3] Running AI analysis (BSE/NSE as primary sources) …")
    prompt = ANALYSIS_PROMPT_TEMPLATE.format(
        company_name       = company_name,
        stock_symbol       = stock_symbol,
        bse_code           = bse_code,
        nse_symbol         = nse_symbol,
        report_date        = report_date,
        bse_slug           = bse_slug,
        screener_url       = args.screener,
        groww_section      = groww_section,
        screener_data      = screener_context,
        groww_data_section = groww_data_section,
    )
    report = run_copilot_analysis(prompt, model_id)

    # 3. Assemble final report: header + AI analysis + raw Screener data section
    groww_ref = f" · [Groww]({args.groww})" if args.groww else ""
    header = (
        f"# {company_name} ({stock_symbol}) — Equity Research Report\n\n"
        f"| | |\n|---|---|\n"
        f"| **Generated** | {report_date} |\n"
        f"| **Model** | {model_id} |\n"
        f"| **BSE Code** | {bse_code} |\n"
        f"| **NSE Symbol** | {nse_symbol} |\n"
        f"| **Primary sources** | [BSE India](https://www.bseindia.com) · [NSE India](https://www.nseindia.com) |\n"
        f"| **Reference links** | [Screener.in]({args.screener}){groww_ref} |\n\n"
        "---\n\n"
    )
    screener_section = "\n\n---\n\n" + format_screener_report(metadata, screener_data)
    full_report = header + report + screener_section

    # print("\n" + "=" * 60)
    # print(full_report)
    # print("=" * 60)

    if args.save:
        with open(args.save, "w", encoding="utf-8") as f:
            f.write(full_report)
        print(f"\n  [saved] Report written to: {args.save}")

    if args.no_email:
        _print_timing_summary(script_start)
        print("\n[Email skipped — remove --no-email to send.]\n")
        return

    # 4. Send email (on by default)
    print("\n[3/3] Sending email …")
    subject   = f"[Stock Analysis] {company_name} ({stock_symbol}) — {report_date}"
    body_html = report_to_html(full_report)
    try:
        send_email(subject, full_report, body_html)
    except smtplib.SMTPAuthenticationError:
        print("\n  [email ERROR] Authentication failed.")
        print("  Use a Gmail App Password: https://support.google.com/accounts/answer/185833")
        sys.exit(1)
    except Exception as e:
        print(f"\n  [email ERROR] {e}")
        sys.exit(1)

    print(f"\n  ✓ Report emailed to {EMAIL_CONFIG['recipient_email']}")
    _print_timing_summary(script_start)


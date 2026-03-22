"""Web scraping utilities for Screener.in and Groww with retry/rate-limit handling."""

import re
import time
from dataclasses import dataclass, field
from typing import Optional

import requests
from bs4 import BeautifulSoup, Tag

from .config import HEADERS, RETRY_DELAYS

_OK   = "✓"
_ERR  = "✗"
_WARN = "~"


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class CompanyMetadata:
    """Identifiers extracted from Screener.in — used to auto-fill CLI args."""
    name: str = ""
    symbol: str = ""
    bse_code: str = ""
    nse_symbol: str = ""

    def is_complete(self) -> bool:
        return bool(self.name and self.symbol)


@dataclass
class ScreenerData:
    """All structured data extracted from a Screener.in company page."""

    # ── Snapshot ratios (top-ratios) ──────────────────────────────────────────
    market_cap: str = ""
    current_price: str = ""
    high_low: str = ""
    stock_pe: str = ""
    book_value: str = ""
    dividend_yield: str = ""
    roce: str = ""
    roe: str = ""
    face_value: str = ""

    # ── Derived / computed ────────────────────────────────────────────────────
    debt_to_equity: str = ""        # latest: Borrowings / (Equity + Reserves)
    interest_coverage: str = ""     # latest annual: Operating Profit / Interest
    pledged_pct: str = ""           # extracted from Cons text

    # ── Compounded growth (ranges-table inside #profit-loss) ──────────────────
    compounded_sales_growth: dict = field(default_factory=dict)    # {10Y, 5Y, 3Y, TTM}
    compounded_profit_growth: dict = field(default_factory=dict)
    stock_price_cagr: dict = field(default_factory=dict)           # {10Y, 5Y, 3Y, 1Y}
    return_on_equity_history: dict = field(default_factory=dict)   # {10Y, 5Y, 3Y, LastYear}

    # ── Tables (list of rows, each row is a list of strings) ──────────────────
    quarters_headers: list = field(default_factory=list)
    quarters_rows: list = field(default_factory=list)       # quarterly P&L

    annual_pl_headers: list = field(default_factory=list)
    annual_pl_rows: list = field(default_factory=list)      # annual P&L

    cash_flow_headers: list = field(default_factory=list)
    cash_flow_rows: list = field(default_factory=list)      # annual cash flows

    balance_sheet_headers: list = field(default_factory=list)
    balance_sheet_rows: list = field(default_factory=list)

    ratios_headers: list = field(default_factory=list)
    ratios_rows: list = field(default_factory=list)         # CCC, WC days, ROCE% etc.

    shareholding_headers: list = field(default_factory=list)
    shareholding_rows: list = field(default_factory=list)   # quarterly shareholding

    # ── Qualitative ───────────────────────────────────────────────────────────
    about: str = ""
    pros: list = field(default_factory=list)
    cons: list = field(default_factory=list)


# ── Helpers ───────────────────────────────────────────────────────────────────

def safe_text(tag) -> str:
    """Return stripped text from a BeautifulSoup tag, or empty string."""
    return tag.get_text(separator=" ", strip=True) if tag else ""


def _log(sym: str, label: str, detail: str = "") -> None:
    suffix = f": {detail}" if detail else ""
    print(f"    {sym}  {label}{suffix}")


def _extract_table(section: Tag, selector: str = "table.data-table") -> tuple[list, list]:
    """Return (headers, data_rows) from the first matching table in section."""
    table = section.select_one(selector)
    if not table:
        return [], []
    headers, rows = [], []
    for i, tr in enumerate(table.find_all("tr")):
        cells = [td.get_text(separator=" ", strip=True) for td in tr.find_all(["th", "td"])]
        if not any(cells):
            continue
        if i == 0:
            headers = cells
        else:
            rows.append(cells)
    return headers, rows


def _compute_growth(values: list[str], years_back: int) -> Optional[str]:
    """Compute CAGR between two annual data points. Returns '±X.X%' or None."""
    nums = []
    for v in values:
        try:
            nums.append(float(v.replace(",", "").replace("%", "").strip()))
        except (ValueError, AttributeError):
            nums.append(None)
    # Need at least (years_back+1) numeric values from the end
    valid = [(i, n) for i, n in enumerate(nums) if n is not None]
    if len(valid) < years_back + 1:
        return None
    end_val = valid[-1][1]
    start_val = valid[-(years_back + 1)][1]
    if start_val <= 0 or end_val <= 0:
        return None
    cagr = ((end_val / start_val) ** (1.0 / years_back) - 1) * 100
    return f"{cagr:+.1f}%"


def _table_row_values(rows: list[list[str]], label: str) -> list[str]:
    """Return data cells of the first row whose first cell matches label."""
    for row in rows:
        if row and label.lower() in row[0].lower():
            return row[1:]
    return []


# ── Core extraction ───────────────────────────────────────────────────────────

def _extract_screener_metadata(url: str, soup: BeautifulSoup) -> CompanyMetadata:
    meta = CompanyMetadata()

    m = re.search(r"/company/([^/]+)", url)
    if m:
        meta.symbol = m.group(1).upper().strip()

    h1 = soup.select_one("h1")
    if h1:
        meta.name = safe_text(h1)

    for a in soup.select("a[href*='bseindia.com']"):
        href = a.get("href", "")
        m = re.search(r"/(\d{6})/?(?:[?#]|$)", href)
        if m:
            meta.bse_code = m.group(1)
            break

    for a in soup.select("a[href*='nseindia.com']"):
        href = a.get("href", "")
        m = re.search(r"[?&]symbol=([A-Z0-9]+)", href, re.IGNORECASE)
        if m:
            meta.nse_symbol = m.group(1).upper()
            break
        m = re.search(r"/equity/([A-Z0-9]{2,20})(?:[/?&]|$)", href, re.IGNORECASE)
        if m:
            meta.nse_symbol = m.group(1).upper()
            break

    if not meta.nse_symbol and meta.symbol:
        meta.nse_symbol = meta.symbol

    return meta


def _extract_screener_data(soup: BeautifulSoup) -> ScreenerData:
    """Extract every structured field from a Screener.in parsed page."""
    d = ScreenerData()

    # ── 1. Top ratios ─────────────────────────────────────────────────────────
    print("  ├─ [1/9] Snapshot ratios")
    ratio_map = {}
    for li in soup.select("ul#top-ratios li"):
        lbl = safe_text(li.select_one(".name"))
        val = safe_text(li.select_one(".value") or li.select_one("span:last-child"))
        if lbl and val:
            ratio_map[lbl.lower()] = val

    field_map = {
        "market_cap": "market cap", "current_price": "current price",
        "high_low": "high / low", "stock_pe": "stock p/e",
        "book_value": "book value", "dividend_yield": "dividend yield",
        "roce": "roce", "roe": "roe", "face_value": "face value",
    }
    found_ratios = []
    for attr, key in field_map.items():
        val = ratio_map.get(key, "")
        setattr(d, attr, val)
        if val:
            found_ratios.append(f"{key.title()}={val}")
    if found_ratios:
        _log(_OK, f"{len(found_ratios)} ratios", ", ".join(found_ratios[:5]) + ("…" if len(found_ratios) > 5 else ""))
    else:
        _log(_ERR, "Snapshot ratios: none found")

    # ── 2. About text ─────────────────────────────────────────────────────────
    print("  ├─ [2/9] About text")
    about_tag = soup.select_one("div.company-profile p") or soup.select_one("#about p")
    if about_tag:
        d.about = safe_text(about_tag)[:600]
        _log(_OK, f"{len(d.about)} chars")
    else:
        _log(_ERR, "not found")

    # ── 3. Compounded growth tables ───────────────────────────────────────────
    print("  ├─ [3/9] Compounded growth / CAGR")
    pl_section = soup.select_one("#profit-loss")
    growth_tables_found = 0
    if pl_section:
        for tbl in pl_section.select("table.ranges-table"):
            header = safe_text(tbl.select_one("th"))
            rows_data = {
                safe_text(tr.select_one("td:first-child")): safe_text(tr.select_one("td:last-child"))
                for tr in tbl.select("tr")
                if tr.select("td")
            }
            if "compounded sales" in header.lower():
                d.compounded_sales_growth = rows_data; growth_tables_found += 1
            elif "compounded profit" in header.lower():
                d.compounded_profit_growth = rows_data; growth_tables_found += 1
            elif "stock price" in header.lower():
                d.stock_price_cagr = rows_data; growth_tables_found += 1
            elif "return on equity" in header.lower():
                d.return_on_equity_history = rows_data; growth_tables_found += 1
    sym = _OK if growth_tables_found == 4 else (_WARN if growth_tables_found > 0 else _ERR)
    _log(sym, f"{growth_tables_found}/4 tables found",
         f"Sales={d.compounded_sales_growth.get('5 Years:', '?')} Profit={d.compounded_profit_growth.get('5 Years:', '?')} PriceCagr={d.stock_price_cagr.get('5 Years:', '?')}")

    # ── 4. Quarterly P&L ──────────────────────────────────────────────────────
    print("  ├─ [4/9] Quarterly results")
    q_sec = soup.select_one("#quarters")
    if q_sec:
        d.quarters_headers, d.quarters_rows = _extract_table(q_sec)
        _log(_OK if d.quarters_rows else _ERR,
             f"{len(d.quarters_rows)} rows × {len(d.quarters_headers)} quarters",
             f"rows: {[r[0] for r in d.quarters_rows][:5]}")
    else:
        _log(_ERR, "#quarters section not found")

    # ── 5. Annual P&L ─────────────────────────────────────────────────────────
    print("  ├─ [5/9] Annual P&L")
    if pl_section:
        d.annual_pl_headers, d.annual_pl_rows = _extract_table(pl_section)
        _log(_OK if d.annual_pl_rows else _ERR,
             f"{len(d.annual_pl_rows)} rows × {len(d.annual_pl_headers)} years")
        # Derived: interest coverage = Operating Profit / Interest (latest year)
        op_vals = _table_row_values(d.annual_pl_rows, "Operating Profit")
        int_vals = _table_row_values(d.annual_pl_rows, "Interest")
        try:
            op  = float(op_vals[-2].replace(",", ""))   # -2 to skip TTM if present
            itr = float(int_vals[-2].replace(",", ""))
            if itr > 0:
                d.interest_coverage = f"{op / itr:.1f}x"
                _log(_OK, f"Computed Interest Coverage = {d.interest_coverage}")
            else:
                d.interest_coverage = "N/A (zero interest)"
        except (IndexError, ValueError, ZeroDivisionError):
            d.interest_coverage = "[not computable]"
            _log(_WARN, f"Interest Coverage not computable (op={op_vals[-2:]} int={int_vals[-2:]})")
    else:
        _log(_ERR, "#profit-loss section not found")

    # ── 6. Cash flows ─────────────────────────────────────────────────────────
    print("  ├─ [6/9] Cash flows")
    cf_sec = soup.select_one("#cash-flow")
    if cf_sec:
        d.cash_flow_headers, d.cash_flow_rows = _extract_table(cf_sec)
        _log(_OK if d.cash_flow_rows else _ERR,
             f"{len(d.cash_flow_rows)} rows × {len(d.cash_flow_headers)} years",
             f"rows: {[r[0] for r in d.cash_flow_rows]}")
    else:
        _log(_ERR, "#cash-flow section not found")

    # ── 7. Balance sheet + D/E ────────────────────────────────────────────────
    print("  ├─ [7/9] Balance sheet + D/E")
    bs_sec = soup.select_one("#balance-sheet")
    if bs_sec:
        d.balance_sheet_headers, d.balance_sheet_rows = _extract_table(bs_sec)
        _log(_OK if d.balance_sheet_rows else _ERR,
             f"{len(d.balance_sheet_rows)} rows × {len(d.balance_sheet_headers)} years")
        # Compute D/E from latest year
        borr  = _table_row_values(d.balance_sheet_rows, "Borrowings")
        equity = _table_row_values(d.balance_sheet_rows, "Equity Capital")
        resrv  = _table_row_values(d.balance_sheet_rows, "Reserves")
        try:
            b = float(borr[-2].replace(",", ""))
            e = float(equity[-2].replace(",", ""))
            r = float(resrv[-2].replace(",", ""))
            net_worth = e + r
            if net_worth > 0:
                d.debt_to_equity = f"{b / net_worth:.2f}x"
                _log(_OK, f"Computed D/E = {d.debt_to_equity}")
            else:
                d.debt_to_equity = "N/A (negative net worth)"
        except (IndexError, ValueError, ZeroDivisionError):
            d.debt_to_equity = "[not computable]"
            _log(_WARN, "D/E not computable")
    else:
        _log(_ERR, "#balance-sheet section not found")

    # ── 8. Ratios (CCC, WC Days) ──────────────────────────────────────────────
    print("  ├─ [8/9] Efficiency ratios (CCC, WC Days)")
    rt_sec = soup.select_one("#ratios")
    if rt_sec:
        d.ratios_headers, d.ratios_rows = _extract_table(rt_sec)
        ccc_row = _table_row_values(d.ratios_rows, "Cash Conversion Cycle")
        wc_row  = _table_row_values(d.ratios_rows, "Working Capital Days")
        _log(_OK if d.ratios_rows else _ERR,
             f"{len(d.ratios_rows)} rows",
             f"CCC latest={ccc_row[-1] if ccc_row else '?'}, WCDays latest={wc_row[-1] if wc_row else '?'}")
    else:
        _log(_ERR, "#ratios section not found")

    # ── 9. Shareholding + pledged ─────────────────────────────────────────────
    print("  ├─ [9/9] Shareholding + Pros/Cons/Pledged")
    shp_sec = soup.select_one("#quarterly-shp")
    if shp_sec:
        d.shareholding_headers, d.shareholding_rows = _extract_table(shp_sec)
        _log(_OK if d.shareholding_rows else _ERR,
             f"{len(d.shareholding_rows)} categories × {len(d.shareholding_headers)} quarters")
    else:
        _log(_WARN, "#quarterly-shp not found")

    # Pros
    d.pros = [safe_text(li) for li in soup.select("div.pros li")]
    _log(_OK if d.pros else _WARN, f"Pros: {len(d.pros)} items")

    # Cons + pledged extraction
    d.cons = [safe_text(li) for li in soup.select("div.cons li")]
    for con in d.cons:
        m = re.search(r"pledged\s+([\d.]+)%", con, re.IGNORECASE)
        if m:
            d.pledged_pct = m.group(1) + "%"
            break
    _log(_OK if d.cons else _WARN, f"Cons: {len(d.cons)} items" + (f", Pledged={d.pledged_pct}" if d.pledged_pct else ""))

    return d


# ── Markdown formatter ────────────────────────────────────────────────────────

def _sparkline(values: list[str], n: int = 10) -> str:
    """Generate a Unicode sparkline from a list of numeric strings."""
    bars = "▁▂▃▄▅▆▇█"
    nums = []
    for v in values[-n:]:
        try:
            nums.append(float(v.replace(",", "").replace("%", "").strip()))
        except (ValueError, AttributeError):
            pass
    if len(nums) < 2:
        return ""
    lo, hi = min(nums), max(nums)
    if hi == lo:
        return bars[3] * len(nums)
    return "".join(bars[int((x - lo) / (hi - lo) * 7)] for x in nums)


def _fmt_table(headers: list, rows: list, max_cols: int = 8) -> str:
    """Format headers + rows as a Markdown table, showing last max_cols periods."""
    if not headers or not rows:
        return "[Data not available]"
    # Keep first col (label) + last (max_cols-1) period columns
    col_indices = [0] + list(range(max(1, len(headers) - max_cols + 1), len(headers)))
    h = [headers[i] if i < len(headers) else "" for i in col_indices]
    lines = ["| " + " | ".join(h) + " |",
             "| " + " | ".join(["---"] * len(h)) + " |"]
    for row in rows:
        cells = [row[i] if i < len(row) else "" for i in col_indices]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def _fmt_growth_tables(d: ScreenerData) -> str:
    tables = [
        ("Compounded Sales Growth", d.compounded_sales_growth),
        ("Compounded Profit Growth", d.compounded_profit_growth),
        ("Stock Price CAGR", d.stock_price_cagr),
        ("Return on Equity", d.return_on_equity_history),
    ]
    lines = ["| Metric | 10Y | 5Y | 3Y | 1Y/TTM/Last |",
             "|--------|-----|----|----|------------|"]
    for title, data in tables:
        if data:
            v10  = data.get("10 Years:", "[N/A]")
            v5   = data.get("5 Years:", "[N/A]")
            v3   = data.get("3 Years:", "[N/A]")
            vttm = data.get("TTM:", data.get("1 Year:", data.get("Last Year:", "[N/A]")))
            lines.append(f"| {title} | {v10} | {v5} | {v3} | {vttm} |")
        else:
            lines.append(f"| {title} | [N/A] | [N/A] | [N/A] | [N/A] |")
    return "\n".join(lines)


def format_screener_report(meta: CompanyMetadata, d: ScreenerData) -> str:
    """
    Produce a Markdown section with all Screener.in extracted data.
    This is included verbatim in the final report for the user's direct reading.
    """
    spark_sales  = _sparkline(_table_row_values(d.annual_pl_rows, "Sales"))
    spark_profit = _sparkline(_table_row_values(d.annual_pl_rows, "Net Profit"))
    spark_opm    = _sparkline(_table_row_values(d.quarters_rows, "OPM %"))
    spark_q_sales = _sparkline(_table_row_values(d.quarters_rows, "Sales"))
    spark_ccc    = _sparkline(_table_row_values(d.ratios_rows, "Cash Conversion Cycle"))
    spark_roe    = _sparkline(_table_row_values(d.ratios_rows, "ROCE %"))

    lines = [
        f"## 📊 Screener.in Data — {meta.name} ({meta.symbol})",
        "",
        "> Data fetched directly from Screener.in. Cross-verify key figures against BSE/NSE filings.",
        "",

        "### Snapshot Ratios",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Market Cap | {d.market_cap} |",
        f"| Current Price | {d.current_price} |",
        f"| 52W High / Low | {d.high_low} |",
        f"| Stock P/E | {d.stock_pe} |",
        f"| Book Value | {d.book_value} |",
        f"| Dividend Yield | {d.dividend_yield} |",
        f"| ROCE | {d.roce} |",
        f"| ROE | {d.roe} |",
        f"| Debt-to-Equity | {d.debt_to_equity or '[N/A]'} |",
        f"| Interest Coverage | {d.interest_coverage or '[N/A]'} |",
        f"| Pledged % | {d.pledged_pct or '0% / not mentioned'} |",
        "",

        "### Compounded Growth & CAGR",
        _fmt_growth_tables(d),
        "",

        "### Quarterly P&L Trend" + (f"  `Sales: {spark_q_sales}`  `OPM%: {spark_opm}`" if spark_q_sales else ""),
        _fmt_table(d.quarters_headers, d.quarters_rows),
        "",

        "### Annual P&L" + (f"  `Sales: {spark_sales}`  `Profit: {spark_profit}`" if spark_sales else ""),
        _fmt_table(d.annual_pl_headers, d.annual_pl_rows),
        "",

        "### Cash Flows (Annual)",
        _fmt_table(d.cash_flow_headers, d.cash_flow_rows),
        "",

        "### Balance Sheet (Annual)",
        _fmt_table(d.balance_sheet_headers, d.balance_sheet_rows),
        "",

        "### Efficiency Ratios — CCC & Working Capital" + (f"  `CCC: {spark_ccc}`  `ROCE%: {spark_roe}`" if spark_ccc else ""),
        _fmt_table(d.ratios_headers, d.ratios_rows),
        "",

        "### Shareholding Pattern (Quarterly)",
        _fmt_table(d.shareholding_headers, d.shareholding_rows),
        "",

        "### Pros (Screener Checklist)",
        "\n".join(f"- ✅ {p}" for p in d.pros) if d.pros else "[None found]",
        "",

        "### Cons (Screener Checklist)",
        "\n".join(f"- ⚠️ {c}" for c in d.cons) if d.cons else "[None found]",
        "",

        "### About",
        d.about or "[Not available]",
    ]
    return "\n".join(lines)


# ── Fetch helpers ─────────────────────────────────────────────────────────────

def fetch_with_retry(url: str, label: str) -> requests.Response | None:
    """GET a URL with exponential backoff on 429 or transient errors."""
    for attempt, delay in enumerate([0] + RETRY_DELAYS, start=1):
        if delay:
            print(f"  [scraper] {label} — retrying in {delay}s "
                  f"(attempt {attempt}/{len(RETRY_DELAYS)+1}) …")
            time.sleep(delay)
        try:
            resp = requests.get(url, headers=HEADERS, timeout=20)
            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", delay or 10))
                print(f"  [scraper] {label} — HTTP 429, waiting {retry_after}s …")
                time.sleep(retry_after)
                continue
            resp.raise_for_status()
            return resp
        except requests.RequestException as exc:
            print(f"  [scraper] {label} — request error: {exc}")
    print(f"  [scraper] {label} — all retry attempts exhausted, skipping.")
    return None


# ── Public API ────────────────────────────────────────────────────────────────

def scrape_screener(url: str) -> tuple[CompanyMetadata, ScreenerData, str]:
    """
    Fetch a Screener.in company page and return:
      - CompanyMetadata : auto-detected name, symbol, BSE code, NSE symbol
      - ScreenerData    : all structured extracted fields
      - str             : compact text summary for the AI prompt context

    Logs each extraction step to the console with ✓ / ✗ / ~ indicators.
    """
    print(f"\n  ┌─ [Screener.in] {url}")
    resp = fetch_with_retry(url, "Screener.in")

    if resp is None:
        print(f"  └─ {_ERR}  FAILED — page could not be fetched\n")
        empty = ScreenerData()
        return CompanyMetadata(), empty, "[Screener.in: could not fetch — rate-limited or unavailable]"

    print(f"    {_OK}  HTTP {resp.status_code} — {len(resp.content):,} bytes received")

    soup = BeautifulSoup(resp.text, "lxml")

    print("  ├─ Metadata")
    metadata = _extract_screener_metadata(url, soup)
    sym = _OK if metadata.name else _ERR
    print(f"    {sym}  name={metadata.name!r}  symbol={metadata.symbol!r}  "
          f"bse={metadata.bse_code or '(none)'}  nse={metadata.nse_symbol!r}")

    data = _extract_screener_data(soup)

    total_chars = len(format_screener_report(metadata, data))
    status_sym = _OK if metadata.is_complete() and data.stock_pe else _WARN
    print(f"  └─ {status_sym}  Done — ~{total_chars:,} chars extracted\n")

    # Compact AI context (top ratios + growth + pros/cons)
    context_lines = ["[Screener.in supplementary data — verify against BSE/NSE]\n"]
    context_lines += [f"{k}: {v}" for k, v in {
        "Market Cap": data.market_cap, "Price": data.current_price,
        "Stock P/E": data.stock_pe, "Book Value": data.book_value,
        "ROE": data.roe, "ROCE": data.roce, "Dividend Yield": data.dividend_yield,
        "D/E": data.debt_to_equity, "Interest Coverage": data.interest_coverage,
        "Pledged": data.pledged_pct,
    }.items() if v]
    if data.compounded_sales_growth:
        context_lines.append(f"Sales CAGR (5Y/3Y): {data.compounded_sales_growth.get('5 Years:','?')} / {data.compounded_sales_growth.get('3 Years:','?')}")
    if data.compounded_profit_growth:
        context_lines.append(f"Profit CAGR (5Y/3Y): {data.compounded_profit_growth.get('5 Years:','?')} / {data.compounded_profit_growth.get('3 Years:','?')}")
    if data.stock_price_cagr:
        context_lines.append(f"Stock Price CAGR (5Y/1Y): {data.stock_price_cagr.get('5 Years:','?')} / {data.stock_price_cagr.get('1 Year:','?')}")
    if data.pros:
        context_lines += [f"PRO: {p}" for p in data.pros]
    if data.cons:
        context_lines += [f"CON: {c}" for c in data.cons]

    return metadata, data, "\n".join(context_lines)


def scrape_groww(url: str) -> str:
    """Scrape supplementary data from a Groww stock page."""
    print(f"\n  ┌─ [Groww] {url}")
    resp = fetch_with_retry(url, "Groww")

    if resp is None:
        print(f"  └─ {_ERR}  FAILED — page could not be fetched\n")
        return "[Groww: could not fetch page after retries — rate-limited or unavailable]"

    print(f"    {_OK}  HTTP {resp.status_code} — {len(resp.content):,} bytes received")

    soup = BeautifulSoup(resp.text, "lxml")
    sections = []

    price_tag = (
        soup.select_one("div.currentPrice")
        or soup.select_one("[class*='currentPrice']")
        or soup.select_one("[class*='livePrice']")
    )
    if price_tag:
        sections.append(f"Current Price: {safe_text(price_tag)}")
        print(f"    {_OK}  Live price found")
    else:
        print(f"    {_WARN}  Live price: [not found — may be JS-rendered]")

    fund_rows = soup.select(
        "[class*='fundamentalRow'], [class*='keyStats'] li, [class*='stockDetail'] li"
    )[:30]
    count_before = len(sections)
    for row in fund_rows:
        text = safe_text(row)
        if text and len(text) < 120:
            sections.append(text)
    fund_count = len(sections) - count_before
    print(f"    {'✓' if fund_count else '~'}  Fundamental rows: {fund_count} extracted")

    tables_found = 0
    for table in soup.find_all("table")[:2]:
        rows = []
        for tr in table.find_all("tr")[:10]:
            cells = [safe_text(td) for td in tr.find_all(["th", "td"])]
            if any(cells):
                rows.append(" | ".join(cells))
        if rows:
            sections.append("\n" + "\n".join(rows))
            tables_found += 1
    print(f"    {'✓' if tables_found else '~'}  Tables: {tables_found} found")

    if len(sections) < 5:
        count_before = len(sections)
        for p in soup.find_all(["p", "span"], limit=200):
            txt = safe_text(p)
            if re.search(r"\d", txt) and 20 < len(txt) < 150:
                sections.append(txt)
        sections = sections[:40]
        print(f"    {_WARN}  Fallback numeric text: {len(sections) - count_before} snippets")

    total_chars = sum(len(s) for s in sections)
    status_sym = _OK if len(sections) >= 5 else _WARN
    print(f"  └─ {status_sym}  Done — {len(sections)} sections, ~{total_chars:,} chars\n")

    return (
        "NOTE: Supplementary data from Groww — verify against BSE/NSE.\n\n"
        + ("\n".join(sections) if sections else "[No structured data extracted from Groww]")
    )


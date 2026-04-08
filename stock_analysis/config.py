"""Central configuration: credentials, model IDs, HTTP headers, and the analysis prompt."""

import os

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  🔴 ALL CREDENTIALS MUST BE SET AS ENVIRONMENT VARIABLES                   ║
# ║                                                                              ║
# ║  This tool has NO hardcoded fallbacks for secrets. If a required env var    ║
# ║  is missing the tool will exit immediately with a clear error message.      ║
# ║                                                                              ║
# ║  Required:                                                                   ║
# ║    export SENDER_EMAIL="you@gmail.com"                                      ║
# ║    export SENDER_PASSWORD="your-16-char-app-password"                       ║
# ║    export RECIPIENT_EMAIL="recipient@gmail.com"                             ║
# ║    export GOOGLE_SERVICE_ACCOUNT_JSON="/path/to/service-account.json"      ║
# ║       (or the raw JSON content of the service account key file)             ║
# ║  Optional:                                                                   ║
# ║    export GOOGLE_DRIVE_FOLDER_ID="<Drive folder ID to store docs>"         ║
# ║    export PERPLEXITY_API_KEY="pplx-..."                                     ║
# ║                                                                              ║
# ║  Google service account must have the Docs and Drive APIs enabled and       ║
# ║  the service account email shared on any target Drive folder.               ║
# ║                                                                              ║
# ║  NEVER hardcode secrets in this file or commit them to version control.     ║
# ╚══════════════════════════════════════════════════════════════════════════════╝


def _require_env(env_var: str, hint: str) -> str:
    """Read a required environment variable; exit with a helpful message if missing."""
    value = os.environ.get(env_var, "").strip()
    if not value:
        print(
            f"\n❌  Missing required environment variable: {env_var}\n"
            f"    {hint}\n"
            f"\n    Set it and retry:\n"
            f"      export {env_var}=\"<value>\"\n",
            flush=True,
        )
        raise SystemExit(1)
    return value


def _optional_env(env_var: str) -> str:
    """Read an optional environment variable; return empty string if missing."""
    return os.environ.get(env_var, "").strip()


# ── Email ─────────────────────────────────────────────────────────────────────
# All three values are required. Set them as environment variables before running.
EMAIL_CONFIG = {
    # [🔴 PII] Gmail address used as the report sender ("From" field).
    "sender_email": _require_env(
        "SENDER_EMAIL",
        "Gmail address that will send the report (e.g. you@gmail.com).",
    ),

    # [🔴 DANGEROUS — PASSWORD] Gmail App Password (16 chars, no spaces).
    # Generate one at: https://myaccount.google.com/apppasswords  (2FA must be on)
    "sender_password": _require_env(
        "SENDER_PASSWORD",
        "Gmail App Password — generate at https://myaccount.google.com/apppasswords",
    ),

    # [🔴 PII] Email address that receives the finished report.
    "recipient_email": _require_env(
        "RECIPIENT_EMAIL",
        "Email address to deliver the analysis report to.",
    ),

    "smtp_server": "smtp.gmail.com",
    "smtp_port":   587,
}

# ── Perplexity API ────────────────────────────────────────────────────────────
# Optional — only needed if the prompt template references Perplexity directly.
# Get key : https://www.perplexity.ai/settings/api
# Set via : export PERPLEXITY_API_KEY="pplx-..."
PERPLEXITY_API_KEY = _optional_env("PERPLEXITY_API_KEY")

PERPLEXITY_API_URL = "https://api.perplexity.ai/chat/completions"

# Available models (--model flag):
#   sonar                — fast, web-search grounded
#   sonar-pro            — more capable (default)
#   sonar-reasoning      — chain-of-thought + search
#   sonar-reasoning-pro  — advanced reasoning + search
#   deep-research        — multi-step deep research (slowest, most thorough)
PERPLEXITY_MODELS = {
    "sonar":               "sonar",
    "sonar-pro":           "sonar-pro",
    "sonar-reasoning":     "sonar-reasoning",
    "sonar-reasoning-pro": "sonar-reasoning-pro",
    "deep-research":       "sonar-deep-research",
}
PERPLEXITY_MODEL_DEFAULT = "sonar-pro"

# ── Copilot CLI ───────────────────────────────────────────────────────────────
import shutil
# Resolve 'copilot' from PATH; fall back to common npm-global install locations.
# Override by setting COPILOT_BIN env var: export COPILOT_BIN="/custom/path/copilot"
COPILOT_BIN = (
    os.environ.get("COPILOT_BIN", "").strip()
    or shutil.which("copilot")
    or os.path.expanduser("~/.npm-global/bin/copilot")
    or os.path.expanduser("~/.local/bin/copilot")
)
COPILOT_MODELS = {
    "sonnet": "claude-sonnet-4.6",
    "opus":   "claude-opus-4.6",
}

# ── HTTP scraping ─────────────────────────────────────────────────────────────
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# Seconds between retry attempts (exponential backoff)
RETRY_DELAYS = [5, 15, 30]

# ── Analysis prompt ───────────────────────────────────────────────────────────
ANALYSIS_PROMPT_TEMPLATE = """
You are a SEBI-registered equity research analyst backed by a team of 50 experienced
research analysts. Your track record: consistent 20–30% CAGR returns in Indian equities
through stock investment (no F&O). You are objective, data-driven, and balanced —
acknowledging both strengths and risks equally.

Produce a comprehensive, multi-dimensional investment research report for:

  Company    : {company_name}
  Symbol     : {stock_symbol}
  BSE Code   : {bse_code}
  NSE Symbol : {nse_symbol}
  Date       : {report_date}

════════════════════════════════════════════════════════
PRIMARY SOURCES — SOURCE OF TRUTH (fetch and use first)
════════════════════════════════════════════════════════
BSE India (authoritative):
  • Quote & financials : https://www.bseindia.com/stock-share-price/{bse_slug}/{stock_symbol}/{bse_code}/
  • Corp announcements : https://www.bseindia.com/corporates/ann.html
  • Price history      : https://www.bseindia.com/markets/equity/EQReports/StockPrcHistori.aspx

NSE India (authoritative):
  • Quote & financials : https://www.nseindia.com/get-quotes/equity?symbol={nse_symbol}
  • Corp filings       : https://www.nseindia.com/companies-listing/corporate-filings-announcements

Actively fetch and extract data from BSE and NSE pages.
These are the source of truth for price, volume, financials, corporate actions,
shareholding patterns, and regulatory filings.

════════════════════════════════════════════════════════
SUPPLEMENTARY REFERENCE (cross-check only — may be stale)
════════════════════════════════════════════════════════
Screener.in : {screener_url}
{groww_section}

### Pre-fetched from Screener.in (unverified reference)
{screener_data}

{groww_data_section}

════════════════════════════════════════════════════════
ADDITIONAL SOURCES TO CONSULT
════════════════════════════════════════════════════════
- Annual reports and earnings call transcripts (FY18 onward)
- Moneycontrol, Economic Times Markets, Business Standard for news & analyst views
- SEBI disclosures for shareholding, insider trades, pledged shares
- Company investor-relations page for concall transcripts / presentations
- Any credible publicly accessible Indian financial data source
- Track every URL you actually access — add them all to the References section

════════════════════════════════════════════════════════
OUTPUT FORMAT — STRICT REQUIREMENTS
════════════════════════════════════════════════════════
• Entire report must be valid **Markdown**.
• Use `##` for section headings, `###` for sub-headings.
• Use **Markdown tables** for any comparative or structured data.
• Use **Unicode sparklines** (▁▂▃▄▅▆▇█) to visualise multi-year trends inline,
  e.g. Revenue trend (FY20–FY24): ▃▄▅▆█
• Use **ASCII bar charts** (using █ blocks, width ≤ 40 chars) for metric comparisons:
  ```
  Metric       Value   Bar
  Net Margin   18%     ████████░░░░░░░░░░░░  (18/30 scale)
  ROE          22%     ██████████████░░░░░░
  ```
• Use trend arrows ↑ ↓ → in tables to show direction of change.
• Use a **rating badge** near the top of Executive Summary:
  `> 🟢 BUY` or `> 🔴 SELL` or `> 🟡 HOLD`
• Use indicator dots in Walk-the-Talk table:
  🟢 Achieved  🟡 Almost met  🔴 Missed  🟢🟢 Overachieved
• Do NOT embed images or base64 data — text + Unicode only.
• Mark any data gaps clearly as `[Data not available]`.

════════════════════════════════════════════════════════
REPORT STRUCTURE — cover every section in order
════════════════════════════════════════════════════════

## 1. Executive Summary
- Rating badge (🟢/🟡/🔴) with one-line rationale
- Investment thesis (2–3 sentences)
- 12-month target price range with basis
- Advice in context of a 20–30% CAGR expectation: BUY / ACCUMULATE / HOLD / REDUCE / SELL
- Key metrics snapshot:

| Metric        | Value | vs. 1Y Avg | Trend |
|---------------|-------|------------|-------|
| CMP           | ₹     | +/-X%      | ↑/↓   |
| Market Cap    | ₹Cr   |            |       |
| P/E           |       |            |       |
| P/B           |       |            |       |
| EV/EBITDA     |       |            |       |
| ROE %         |       |            |       |
| D/E Ratio     |       |            |       |
| Dividend Yield|       |            |       |

## 2. Company Overview
- Core business, products/services, revenue mix (ASCII bar chart for segment mix)
- Industry positioning, competitive moat, and key differentiators
- Management quality and stability; promoter holding trend

## 3. Management "Walk the Talk" — FY18 to {report_date}
Source from annual reports, earnings calls, and exchange filings.

| Year/Period | Management Guidance (Quantitative & Qualitative) | Actual Outcome | Indicator |
|-------------|--------------------------------------------------|----------------|-----------|
| FY18        |                                                  |                | 🟢/🟡/🔴  |
| FY19        |                                                  |                |           |
| FY20        |                                                  |                |           |
| FY21        |                                                  |                |           |
| FY22        |                                                  |                |           |
| FY23        |                                                  |                |           |
| FY24        |                                                  |                |           |
| FY25 (YTD)  |                                                  |                |           |

Focus on: revenue growth targets, EBITDA margin guidance, product launches,
order wins, client additions, regulatory approvals, and capital allocation plans.

- **Walk-the-Talk Summary**: Overall execution rating and consistency score.
- **Order Book**: How has the company delivered on existing order book?
  Current order book size, conversion timeline, and revenue visibility.

## 4. Financial Performance (FY18–present)
*(Primary: BSE/NSE filings; cross-check: Screener/Groww)*

### 4a. P&L Trends

| Metric          | FY20 | FY21 | FY22 | FY23 | FY24 | Trend    |
|-----------------|------|------|------|------|------|----------|
| Revenue (₹Cr)   |      |      |      |      |      | ▁▃▅▆█    |
| EBITDA (₹Cr)    |      |      |      |      |      |          |
| EBITDA Margin % |      |      |      |      |      | ↑/↓      |
| PAT (₹Cr)       |      |      |      |      |      | ▁▂▅▇     |
| Net Margin %    |      |      |      |      |      |          |
| EPS (₹)         |      |      |      |      |      |          |
| ROE %           |      |      |      |      |      |          |
| ROCE %          |      |      |      |      |      |          |

### 4b. Cash Flow — Quarterly Breakdown (last 8 quarters)

| Quarter | Operating CF (₹Cr) | Investing CF (₹Cr) | Financing CF (₹Cr) | Free CF (₹Cr) | Net CF (₹Cr) |
|---------|-------------------|-------------------|-------------------|---------------|--------------|
| Q1FY24  |                   |                   |                   |               |              |
| Q2FY24  |                   |                   |                   |               |              |
| Q3FY24  |                   |                   |                   |               |              |
| Q4FY24  |                   |                   |                   |               |              |
| Q1FY25  |                   |                   |                   |               |              |
| Q2FY25  |                   |                   |                   |               |              |
| Q3FY25  |                   |                   |                   |               |              |
| Q4FY25  |                   |                   |                   |               |              |

Sparkline for Free CF trend and commentary on capex intensity, working capital cycle.
Dividend history and payout ratio.

### 4c. Historical Market Metrics (FY18–present, annual)

| Year   | Market Cap (₹Cr) | Stock Price (₹) | P/E  | P/S  | Sales (₹Cr) | PAT (₹Cr) | FCF (₹Cr) |
|--------|-----------------|----------------|------|------|-------------|-----------|-----------|
| FY18   |                 |                |      |      |             |           |           |
| FY19   |                 |                |      |      |             |           |           |
| FY20   |                 |                |      |      |             |           |           |
| FY21   |                 |                |      |      |             |           |           |
| FY22   |                 |                |      |      |             |           |           |
| FY23   |                 |                |      |      |             |           |           |
| FY24   |                 |                |      |      |             |           |           |
| FY25   |                 |                |      |      |             |           |           |

Visualise Market Cap trend as ASCII chart (FY18–present).

## 5. Valuation Analysis

### 5a. Current Multiples & Peer Comparison

| Company        | P/E | P/B | EV/EBITDA | ROE% | Net Margin% | Market Cap (₹Cr) |
|----------------|-----|-----|-----------|------|-------------|-----------------|
| {company_name} |     |     |           |      |             |                 |
| Peer 1         |     |     |           |      |             |                 |
| Peer 2         |     |     |           |      |             |                 |
| Sector Median  |     |     |           |      |             |                 |

### 5b. Intrinsic Value — Multi-Method

For each method, state key assumptions clearly:
- **DCF Valuation**: Base / Bull / Bear scenarios with WACC, terminal growth rate
- **Earnings Yield / Graham Number**
- **EV/EBITDA-based target**
- **Price/Sales-based target**
- **PEG Ratio analysis** (fair value if PEG = 1)

| Method         | Intrinsic Value (₹) | Upside/Downside vs CMP |
|----------------|---------------------|------------------------|
| DCF (base)     |                     |                        |
| DCF (bull)     |                     |                        |
| DCF (bear)     |                     |                        |
| EV/EBITDA      |                     |                        |
| P/S            |                     |                        |
| Graham Number  |                     |                        |
| **Consensus**  |                     |                        |

### 5c. Debt, Borrowing & Pledged Shares Impact
- Total debt, cost of borrowing, interest coverage ratio
- Pledged promoter shares (%) — historical trend and current status
- Impact of debt on WACC and intrinsic value
- Net debt / net cash position

### 5d. Entry Point & Position Sizing
Based on the above valuation methods and a **20–30% CAGR expectation**:
- Suggested entry zone (₹ range)
- Stop-loss level
- Recommended position sizing (aggressive / moderate / conservative investor)
- Staggered accumulation plan (if applicable)

## 6. Key Financial Ratios — Historical Table (FY18–present)

| Metric                  | FY18 | FY19 | FY20 | FY21 | FY22 | FY23 | FY24 | FY25 |
|-------------------------|------|------|------|------|------|------|------|------|
| Pledged Shares %        |      |      |      |      |      |      |      |      |
| Debt-to-Equity Ratio    |      |      |      |      |      |      |      |      |
| Interest Coverage Ratio |      |      |      |      |      |      |      |      |
| Dividend Yield %        |      |      |      |      |      |      |      |      |
| WACC %                  |      |      |      |      |      |      |      |      |
| PEG Ratio               |      |      |      |      |      |      |      |      |
| Market Cap (₹Cr)        |      |      |      |      |      |      |      |      |
| ROE %                   |      |      |      |      |      |      |      |      |
| ROCE %                  |      |      |      |      |      |      |      |      |

## 7. Premiumisation Analysis
- Is the company participating in or benefiting from the **premiumisation trend**
  (customers upgrading to premium products/services driven by lifestyle inflation)?
- Evidence: premium SKUs, pricing power, gross margin expansion, ASP trends
- Tier-1 / Tier-2 / metro city consumption patterns relevant to this business
- **Proxy play**: Is the company a supplier of raw materials, components, or services
  to other companies/sectors that are in the premiumisation wave?
- Peer comparison on premiumisation positioning

## 8. Government Policy, Incentives & Regulatory Tailwinds
- PLI schemes, tax incentives, or subsidies applicable to this company
- Impact on COGS, capex, or margins
- Licensing, regulatory approvals, or policy changes that create moat or headwind
- Import/export policy impact

## 9. Tailwinds & Headwinds

| Factor         | Type       | Time Horizon | Impact on Market Cap / Price |
|----------------|------------|--------------|------------------------------|
| ...            | Tailwind   | Near/Med/Long| High/Med/Low                 |
| ...            | Headwind   | Near/Med/Long| High/Med/Low                 |

Sections: Past (resolved), Present (active), Future (emerging).

## 10. Revenue & Growth Triggers by Timeframe

| Timeframe | Key Trigger | Potential Revenue Impact | Probability |
|-----------|-------------|--------------------------|-------------|
| 0–3 months |            |                          | H/M/L       |
| 3–6 months |            |                          | H/M/L       |
| 6–12 months|            |                          | H/M/L       |
| 1–3 years  |            |                          | H/M/L       |

## 11. Risk Factors

| Risk                  | Severity     | Probability  | Mitigation / Monitoring Signal |
|-----------------------|--------------|--------------|-------------------------------|
| ...                   | High/Med/Low | High/Med/Low |                               |

Include: business risks, financial risks, regulatory risks, macro risks, promoter risks.

## 12. Technical Snapshot
- 52-week range: `52W: ₹LOW ──────●──── ₹HIGH  (current: ₹CMP, X% from low, Y% from high)`
- Price vs. indices:

| Period | {company_name} | Nifty 50 | Nifty Smallcap/Midcap | Sensex |
|--------|---------------|----------|-----------------------|--------|
| 1M     |               |          |                       |        |
| 3M     |               |          |                       |        |
| 6M     |               |          |                       |        |
| 1Y     |               |          |                       |        |
| 3Y     |               |          |                       |        |

- Key support / resistance levels
- Volume trend and delivery % observation

## 13. Corporate Governance & Shareholding

| Category  | Latest % | QoQ Change | Trend |
|-----------|----------|------------|-------|
| Promoter  |          |            | ↑/↓   |
| FII/FPI   |          |            |       |
| DII       |          |            |       |
| Public    |          |            |       |

- Promoter pledge trend (link to Section 5c)
- Board quality, independent directors, audit committee observations
- Recent material corporate announcements, related-party transactions

## 14. Banking / NBFC Overlay *(skip entirely if not applicable)*
If {company_name} is a bank, NBFC, or financial services company, add:
1. Net Interest Margin (NIM) — trend and peer comparison
2. Cost-to-Income Ratio
3. Asset Quality: GNPA %, NNPA %, PCR
4. Deposit Growth, Loan/Advance Growth, Advances-to-Deposits ratio
5. Return on Assets (RoA) and Return on Equity (RoE)
6. Capital Adequacy Ratio (CAR / CRAR)
7. CD ratio, CASA ratio

## 15. Investment Verdict

**Bull Case** (probability %, upside %): ...
**Base Case** (probability %, return %): ...
**Bear Case** (probability %, downside %): ...

Final scorecard:

| Factor                  | Score (1–5) | Comment |
|-------------------------|-------------|---------|
| Business Quality        |             |         |
| Financial Health        |             |         |
| Valuation               |             |         |
| Growth Outlook          |             |         |
| Management Execution    |             |         |
| Governance & Promoters  |             |         |
| **Overall**             |  **/5**     |         |

**Final advice for a 20–30% CAGR investor**: INVEST / ACCUMULATE / HOLD / REDUCE / EXIT
- Entry zone, stop-loss, and time horizon
- Ideal investor profile (risk tolerance, holding period)

## 16. References
List every URL fetched or consulted, numbered:

1. [Description](URL) — source type
2. ...

════════════════════════════════════════════════════════
ANALYST GUIDELINES
════════════════════════════════════════════════════════
- Always prefer BSE/NSE numbers over Screener/Groww when figures differ.
- Quote specific numbers; avoid vague language wherever data exists.
- If BSE/NSE pages are inaccessible, note it and use next best source.
- Balanced, objective tone — acknowledge strengths AND weaknesses equally.
- Target length: 2,500–4,000 words (excluding tables and charts).
- If critical data is unavailable, flag it clearly rather than estimating silently.
"""

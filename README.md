# Stock Analysis Tool 📈

AI-powered Indian equity research tool. Paste a Screener.in URL → get a detailed
16-section research report in your inbox, including scraped fundamentals, historical
ratios, valuation estimates, and a buy/hold/sell verdict.

---

## Features

- **Auto-detects** company name, NSE/BSE symbol from the Screener.in URL — works for
  micro-cap, small-cap, and large-cap companies alike.
- **Scrapes** 9 data sections from Screener.in: snapshot ratios, compounded growth
  tables, quarterly P&L, annual P&L, cash flows, balance sheet, efficiency ratios,
  shareholding pattern, and pros/cons.
- **Builds** a 16-section analysis prompt covering: Walk the Talk (FY18→now),
  multi-method valuation (DCF / Graham / EV / P-S / PEG), debt & pledged shares,
  premiumisation analysis, govt incentives, tailwinds/headwinds, revenue triggers
  by timeframe (3M / 6M / 1Y / 3Y), and an investment verdict with Bull/Base/Bear
  scenarios.
- **Runs** the prompt through the Copilot CLI (Claude Sonnet or Opus).
- **Emails** the formatted HTML report; optionally saves it to a file.
- **Security**: all secrets must be in environment variables — hardcoded fallbacks
  emit `🔴 DANGEROUS` warnings at runtime.

---

## Project Structure

```
stock-analysis1/
├── main.py                     # Entry point
├── requirements.txt            # Python dependencies
├── .gitignore
├── README.md
└── stock_analysis/
    ├── __init__.py
    ├── config.py               # Credentials, models, HTTP headers, prompt template
    ├── scraper.py              # Screener.in / Groww scraping & data extraction
    ├── analyzer.py             # Copilot CLI subprocess wrapper
    ├── email_sender.py         # Markdown → HTML conversion + SMTP sender
    └── cli.py                  # argparse + main orchestration pipeline
```

---

## Prerequisites

- Python 3.10+
- [GitHub Copilot CLI](https://githubnext.com/projects/copilot-cli/) installed and
  authenticated (`copilot` command available on PATH)
- A Gmail account with an [App Password](https://support.google.com/accounts/answer/185833)
  (2FA must be enabled)

### Install Python dependencies

```bash
pip install -r requirements.txt
```

---

## Environment Variables (Required — Never Commit These)

| Variable             | Description                                      | Risk     |
|----------------------|--------------------------------------------------|----------|
| `SENDER_EMAIL`       | Gmail address used to send reports               | 🔴 HIGH  |
| `SENDER_PASSWORD`    | Gmail App Password (16-char, no spaces)          | 🔴 HIGH  |
| `RECIPIENT_EMAIL`    | Email address to receive reports                 | 🟡 MED   |
| `PERPLEXITY_API_KEY` | Perplexity API key (used in prompt context only) | 🔴 HIGH  |

> All three email variables are **required**. If any are missing, the tool exits
> immediately with a clear error message telling you exactly which variable to set.
> There are no hardcoded fallbacks.

### Setting Environment Variables

#### Temporary (current terminal session only)

```bash
export SENDER_EMAIL="you@gmail.com"
export SENDER_PASSWORD="abcd efgh ijkl mnop"
export RECIPIENT_EMAIL="reports@gmail.com"
export PERPLEXITY_API_KEY="pplx-xxxxxxxxxxxxxxxxxxxx"
```

#### Permanent (add to `~/.bashrc` or `~/.zshrc`)

```bash
# Stock Analysis secrets — never commit these
export SENDER_EMAIL="you@gmail.com"
export SENDER_PASSWORD="abcd efgh ijkl mnop"
export RECIPIENT_EMAIL="reports@gmail.com"
export PERPLEXITY_API_KEY="pplx-xxxxxxxxxxxxxxxxxxxx"
```

After editing `~/.bashrc`:
```bash
source ~/.bashrc
```

#### Using a `.env` file (local only — already in `.gitignore`)

```bash
# .env
SENDER_EMAIL=you@gmail.com
SENDER_PASSWORD=abcd efgh ijkl mnop
RECIPIENT_EMAIL=reports@gmail.com
PERPLEXITY_API_KEY=pplx-xxxxxxxxxxxxxxxxxxxx
```

Then load it before running:
```bash
set -a && source .env && set +a
python3 main.py --screener "..."
```

---

## Usage

```
python3 main.py [--name NAME] [--symbol SYMBOL] --screener URL
                [--groww URL] [--model {sonnet,opus}]
                [--no-email] [--save FILE]
```

### Arguments

| Argument        | Required | Description                                                    |
|-----------------|----------|----------------------------------------------------------------|
| `--screener`    | ✅ Yes   | Screener.in company URL (source of truth for data + metadata)  |
| `--name`        | No       | Company name — auto-detected from Screener if omitted          |
| `--symbol`      | No       | NSE/BSE ticker — auto-detected from Screener URL if omitted    |
| `--groww`       | No       | Groww stock URL (supplementary reference)                      |
| `--model`       | No       | `sonnet` (default, faster) or `opus` (more thorough)           |
| `--no-email`    | No       | Skip email — print report to console only                      |
| `--save FILE`   | No       | Save the report to a file (e.g. `report.md`)                   |

---

## Sample Commands

### Large-cap (name & symbol well-known)

```bash
python3 main.py \
  --name "Infosys" --symbol "INFY" \
  --screener "https://www.screener.in/company/INFY/" \
  --groww "https://groww.in/stocks/infosys-ltd"
```

### Micro-cap / small-cap (let the tool auto-detect name & symbol)

```bash
python3 main.py \
  --screener "https://www.screener.in/company/CELLECOR/" \
  --groww "https://groww.in/stocks/cellecor-gadgets-ltd"
```

### Screener URL only (minimal input)

```bash
python3 main.py \
  --screener "https://www.screener.in/company/ALGOQUANT/"
```

### Use Claude Opus for a more thorough analysis

```bash
python3 main.py \
  --screener "https://www.screener.in/company/ALGOQUANT/" \
  --model opus
```

### Save report to file without emailing

```bash
python3 main.py \
  --screener "https://www.screener.in/company/INFY/" \
  --no-email \
  --save infosys_report.md
```

### Print to console (no email, no file)

```bash
python3 main.py \
  --screener "https://www.screener.in/company/TITAN/" \
  --no-email
```

---

## Report Structure (16 Sections)

1. Walk the Talk — management guidance vs. actual outcome (FY18 → present)
2. Financial performance graphs — market cap, P/E, price, sales, profit, FCF
3. Quarterly cash flow breakdown — Operating / Investing / Financing
4. Historical market metrics — market cap, P/E, price trend (FY18 → present)
5. Multi-method valuation — DCF, Graham Number, EV/EBITDA, P/S, PEG
6. Debt & pledged shares analysis — cost of borrowing, interest coverage
7. Entry point & position sizing
8. Historical ratio table — pledged %, interest coverage, D/E, dividend yield, WACC, PEG, market cap (FY18 → present)
9. Premiumisation analysis — is this a premium-play or proxy for premiumisation?
10. Government incentives & policy advantages
11. Tailwinds & headwinds — past, present, future
12. Revenue & growth triggers — 3M / 6M / 1Y / 3Y timeframes
13. Banking / NBFC overlay (NIM, NPA, RoA, RoE, CAR) — shown only for banks
14. Order book & execution track record
15. Screener.in fundamentals — scraped raw data (ratios, growth tables, shareholding, etc.)
16. Investment verdict — Bull / Base / Bear scenarios, Buy / Hold / Sell recommendation

---

## Models

| Key      | Claude Model           | Best For                           |
|----------|------------------------|------------------------------------|
| `sonnet` | claude-sonnet-4.6      | Fast daily analysis (default)      |
| `opus`   | claude-opus-4.6        | Deep-dive research, large prompts  |

---

## Security Notes

- `.gitignore` already excludes `.env`, `__pycache__/`, `*.pyc`, and common editor/OS files.
- **No hardcoded credentials exist in the codebase.** The tool exits immediately with a
  clear error if `SENDER_EMAIL`, `SENDER_PASSWORD`, or `RECIPIENT_EMAIL` are not set.
- Gmail App Passwords are 16 characters without spaces. Do not use your main account password.
- `PERPLEXITY_API_KEY` is optional — the tool runs without it.

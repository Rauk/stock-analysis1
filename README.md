# Stock Analysis Tool 📈

AI-powered Indian equity research tool. Paste a Screener.in URL → get a detailed
16-section research report saved to a Google Doc and delivered to your inbox,
including scraped fundamentals, historical ratios, valuation estimates, and a
buy/hold/sell verdict.

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
- **Google Docs**: automatically creates a dedicated Google Doc per stock (named
  `"Stock Analysis - {SYMBOL}"`). On subsequent runs for the same stock the new
  analysis is prepended to the top of the existing doc and a dated separator line
  keeps the history intact — so every past report remains accessible in one place.
- **Emails** the formatted HTML report with a prominent link to the Google Doc;
  optionally saves the report to a local file.
- **Security**: all secrets must be in environment variables — hardcoded fallbacks
  emit `🔴 DANGEROUS` warnings at runtime.

---

## Project Structure

```
stock-analysis1/
├── main.py                     # Entry point
├── requirements.txt            # Python dependencies
├── run_commands.sh             # Batch parallel runner
├── commandsToExecute.txt       # Commands for the batch runner (edit before running)
├── all_commands.txt            # Master list of all tracked stocks (~48 companies)
├── test_gdocs.py               # Google Docs connectivity tester (no stock processing)
├── logs/                       # Per-run timestamped log folders (auto-created)
├── .gitignore
├── README.md
└── stock_analysis/
    ├── __init__.py
    ├── config.py               # Credentials, models, HTTP headers, prompt template
    ├── scraper.py              # Screener.in / Groww scraping & data extraction
    ├── analyzer.py             # Copilot CLI subprocess wrapper
    ├── google_docs.py          # Google Docs integration (create/update per-stock docs)
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
- A Google Cloud **Service Account** with the **Google Docs API** and **Google Drive API**
  enabled (see [Google Docs Setup](#google-docs-setup) below)

### Install Python dependencies

```bash
pip install -r requirements.txt
```

---

## Environment Variables (Required — Never Commit These)

| Variable                      | Description                                                        | Risk     |
|-------------------------------|--------------------------------------------------------------------|----------|
| `SENDER_EMAIL`                | Gmail address used to send reports                                 | 🔴 HIGH  |
| `SENDER_PASSWORD`             | Gmail App Password (16-char, no spaces)                            | 🔴 HIGH  |
| `RECIPIENT_EMAIL`             | Email address to receive reports                                   | 🟡 MED   |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Path to service account JSON key file, or the raw JSON content     | 🔴 HIGH  |
| `GOOGLE_DRIVE_FOLDER_ID`      | *(Optional)* Drive folder ID where stock docs will be stored       | 🟢 LOW   |
| `PERPLEXITY_API_KEY`          | Perplexity API key (used in prompt context only)                   | 🔴 HIGH  |

> `SENDER_EMAIL`, `SENDER_PASSWORD`, `RECIPIENT_EMAIL`, and
> `GOOGLE_SERVICE_ACCOUNT_JSON` are **required**. If any are missing, the tool exits
> immediately with a clear error message telling you exactly which variable to set.
> There are no hardcoded fallbacks.

### Setting Environment Variables

#### Temporary (current terminal session only)

```bash
export SENDER_EMAIL="you@gmail.com"
export SENDER_PASSWORD="abcd efgh ijkl mnop"
export RECIPIENT_EMAIL="reports@gmail.com"
export GOOGLE_SERVICE_ACCOUNT_JSON="/path/to/service-account.json"
export GOOGLE_DRIVE_FOLDER_ID="1A2B3C4D5E6F7G8H9I0J"   # optional
export PERPLEXITY_API_KEY="pplx-xxxxxxxxxxxxxxxxxxxx"
```

#### Permanent (add to `~/.bashrc` or `~/.zshrc`)

```bash
# Stock Analysis secrets — never commit these
export SENDER_EMAIL="you@gmail.com"
export SENDER_PASSWORD="abcd efgh ijkl mnop"
export RECIPIENT_EMAIL="reports@gmail.com"
export GOOGLE_SERVICE_ACCOUNT_JSON="/path/to/service-account.json"
export GOOGLE_DRIVE_FOLDER_ID="1A2B3C4D5E6F7G8H9I0J"   # optional
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
GOOGLE_SERVICE_ACCOUNT_JSON=/path/to/service-account.json
GOOGLE_DRIVE_FOLDER_ID=1A2B3C4D5E6F7G8H9I0J   # optional
PERPLEXITY_API_KEY=pplx-xxxxxxxxxxxxxxxxxxxx
```

Then load it before running:
```bash
set -a && source .env && set +a
python3 main.py --screener "..."
```

---

## Google Docs Setup

Each stock gets its own Google Doc named `"Stock Analysis - {SYMBOL}"`. On every run:
- If no doc exists for the symbol, a new one is created automatically.
- If a doc already exists, the new analysis is **prepended at the top** and a separator
  line with the execution date is inserted between the new and old content, so the
  full history is preserved in a single document.

The email report includes a prominent **link to the Google Doc** at the top.

### Steps

1. **Create a Google Cloud project** (or use an existing one) at
   [console.cloud.google.com](https://console.cloud.google.com/).

2. **Enable APIs** — in the project, enable:
   - Google Docs API
   - Google Drive API

3. **Create a Service Account**:
   - Go to *IAM & Admin → Service Accounts → Create Service Account*
   - Grant it no special project roles (Drive access is controlled by sharing)
   - Create and download a JSON key file

4. **Share your Drive folder** with the service account email address
   (e.g. `my-sa@my-project.iam.gserviceaccount.com`) with **Editor** access.
   - If you omit `GOOGLE_DRIVE_FOLDER_ID`, docs are created in the service account's
     own Drive (accessible only via the doc URL unless shared further).

5. **Set the environment variable**:
   ```bash
   # Option A — path to the JSON key file
   export GOOGLE_SERVICE_ACCOUNT_JSON="/path/to/service-account.json"

   # Option B — raw JSON content (useful in CI/CD)
   export GOOGLE_SERVICE_ACCOUNT_JSON='{"type":"service_account", ...}'
   ```

6. *(Optional)* Set the target folder:
   ```bash
   export GOOGLE_DRIVE_FOLDER_ID="<folder ID from the Drive URL>"
   ```

> **Tip:** You can disable Google Docs for a single run with `--no-gdocs`.

---

## Testing Google Docs Connectivity

Before running a full stock analysis, use `test_gdocs.py` to verify that your
service account credentials, Google Docs API, and Google Drive API are all
working. It creates or updates a Google Doc with a timestamp and random text
— no stock processing happens.

### Usage

```bash
# Basic test — doc created in service account's own isolated Drive
python3 test_gdocs.py --symbol TEST

# With a shared folder (recommended — doc appears in your Drive)
python3 test_gdocs.py --symbol TEST --folder-id 1ABC123xyz

# Pass folder ID inline (overrides GOOGLE_DRIVE_FOLDER_ID env var)
python3 test_gdocs.py --symbol INFY --folder-id 1ABC123xyz

# Run twice to verify prepend + separator behaviour
python3 test_gdocs.py --symbol TEST --folder-id 1ABC123xyz
python3 test_gdocs.py --symbol TEST --folder-id 1ABC123xyz
```

### Arguments

| Argument       | Required | Description                                               |
|----------------|----------|-----------------------------------------------------------|
| `--symbol`     | ✅ Yes   | Symbol name used as the doc title (`Stock Analysis - X`)  |
| `--folder-id`  | No       | Drive folder ID — overrides `GOOGLE_DRIVE_FOLDER_ID`      |

### Sample Output (success)

```
════════════════════════════════════════════════════════
  Google Docs connectivity test
  Symbol    : TEST
  Timestamp : 2026-04-08 15:30:00
  Folder ID : 1ABC123xyz
════════════════════════════════════════════════════════

[1/2] Getting or creating doc …
  [gdocs] Created new doc for TEST: https://docs.google.com/document/d/abc123/edit

[2/2] Prepending test content …
  [gdocs] Analysis prepended to doc (date: 08 April 2026)

════════════════════════════════════════════════════════
  ✓  Test passed!
  Doc URL : https://docs.google.com/document/d/abc123/edit
════════════════════════════════════════════════════════
```

### Sample Output (403 error — common first-time issue)

```
[1/2] Getting or creating doc …

❌  Failed to get/create doc:
403 Permission denied. To fix:
  1. Go to https://console.cloud.google.com/apis/library
     and enable both 'Google Docs API' and 'Google Drive API' for your project.
  2. Share a Drive folder with the service account email (found in your JSON
     key as 'client_email') with Editor access.
  3. Set GOOGLE_DRIVE_FOLDER_ID to that folder's ID.
```

> **API propagation time:** After enabling APIs and creating the service account,
> wait **1–2 minutes** before running the test. If you still get a 403 after
> 5 minutes, the issue is permissions (folder not shared, wrong project), not
> propagation delay.

---

## Usage

```
python3 main.py [--name NAME] [--symbol SYMBOL] --screener URL
                [--groww URL] [--model {sonnet,opus}]
                [--no-email] [--no-gdocs] [--save FILE]
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
| `--no-gdocs`    | No       | Skip Google Docs update for this run                           |
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

## Batch Parallel Runner

`run_commands.sh` lets you analyse **multiple stocks in parallel** in a single
command. It reads the list of `python3 main.py ...` commands from
`commandsToExecute.txt`, keeps up to **10 jobs running simultaneously**, and
starts the next queued command the moment any slot frees up.

### How it works

1. Commands are read from `commandsToExecute.txt` (blank lines and `#` comments
   are ignored).
2. Up to `MAX_PARALLEL=10` jobs are launched immediately; the rest are queued.
3. As each job completes a new one is started right away — no idle slots.
4. A status table is printed every **20 seconds** showing each company's state
   (`pending` / `running` / `success` / `failed`) and elapsed time.
5. Every run creates a timestamped folder under `logs/` (e.g.
   `logs/run_20260407_093000/`). Each company gets its own `<SYMBOL>.log` file
   inside that folder, containing the full command output.
6. A final summary shows total succeeded / failed counts and the log folder path.

### Workflow

**Step 1 — choose which stocks to analyse**

Copy the commands you want from `all_commands.txt` into `commandsToExecute.txt`,
or write your own. `all_commands.txt` is the master list of ~48 tracked stocks
and is never read directly by the runner.

```bash
# Run all tracked stocks
cp all_commands.txt commandsToExecute.txt

# Or pick a subset — just paste selected lines into commandsToExecute.txt
```

**Step 2 — run the batch**

```bash
chmod +x run_commands.sh
./run_commands.sh
```

**Sample output**

```
════════════════════════════════════════════════════
 Stock Analysis Runner — 20260407_093000
 Commands : 10  |  Max parallel : 10
 Logs     : /path/to/logs/run_20260407_093000
════════════════════════════════════════════════════
  [START] #1 INFY  →  INFY.log
  [START] #2 TCS   →  TCS.log
  ...
── Status Update  2026-04-07 09:30:20 ──────────────
  No.   Company          Status     Duration
  ──────────────────────────────────────────────────
  1     INFY             running    20s
  2     TCS              running    20s
  ...
  [OK]   #1 INFY  (4m12s)
  [FAIL] #3 SOMECO  exit=1  →  SOMECO.log
  ...
════════════════════════════════════════════════════
 Run complete — 20260407_093000
 Succeeded : 9  |  Failed : 1
 Logs      : /path/to/logs/run_20260407_093000
════════════════════════════════════════════════════
```

### Logs

Each run's logs are stored at `logs/run_<YYYYMMDD_HHMMSS>/`. The company name
is extracted automatically from the Screener.in URL slug:

```
logs/
└── run_20260407_093000/
    ├── INFY.log
    ├── TCS.log
    ├── TITAN.log
    └── ...
```

Each log file includes the exact command run, start/end timestamps, the full
AI analysis output, email status, Google Docs update status, and exit code.

### Customising

| Setting          | Where to change              | Default |
|------------------|------------------------------|---------|
| Max parallel jobs | `MAX_PARALLEL` in `run_commands.sh` | `10` |
| Commands to run  | `commandsToExecute.txt`      | —       |
| Master stock list | `all_commands.txt`           | ~48 stocks |

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

## Known Risks & Limitations

### 🔴 `commandsToExecute.txt` is trusted input for `run_commands.sh`

`run_commands.sh` executes commands from `commandsToExecute.txt` using `eval`.
This means **any shell command in that file will be executed**. Only add
`python3 main.py ...` commands to this file. Never allow untrusted users or
automated processes to write to `commandsToExecute.txt`.

### 🔴 `--save FILE` writes to any path you specify

The `--save` argument writes the report to whatever path you provide, including
absolute paths. Use relative paths and filenames only (e.g. `report.md`, not
`/etc/cron.d/report`). There is no directory restriction enforced by the tool.

### 🔴 Service account JSON key must not be committed

`.gitignore` excludes `.env` files but does **not** automatically exclude
`*.json` files. If you place your service account key in the repo directory,
you must add it to `.gitignore` manually or use the env-var approach:

```bash
# Safe — key file outside the repo
export GOOGLE_SERVICE_ACCOUNT_JSON="/home/yourname/keys/sa-key.json"

# Also safe — raw JSON in env var (useful for CI/CD)
export GOOGLE_SERVICE_ACCOUNT_JSON='{"type":"service_account",...}'
```

Never run `git add *.json` without checking what is staged.

### 🟡 URLs are not domain-validated

`--screener` and `--groww` accept any HTTP/HTTPS URL. Only pass URLs from
`screener.in` and `groww.in`. Do not pass internal network addresses or
`file://` URLs.

### 🟡 Parallel batch runs can trigger rate-limiting

Running many stocks in parallel via `run_commands.sh` may cause Screener.in
to rate-limit your IP (HTTP 429). The scraper handles 429s with backoff, but
if you are banned, wait a few hours or reduce `MAX_PARALLEL` in
`run_commands.sh`.

### 🟡 SMTP exceptions may include your email address in error output

If a non-authentication SMTP error occurs (e.g. connection refused), the raw
exception message printed to console/logs may include the sender email address.
Treat log files as sensitive if they may be shared.

### 🟢 What is already safe

- **No hardcoded credentials** — all secrets required via environment variables; tool exits immediately if missing.
- **Subprocess is injection-safe** — Copilot CLI is invoked with a list (not `shell=True`), preventing shell injection via prompt content.
- **Copilot CLI write-access denied** — `--deny-tool=write` prevents the AI from modifying local files.
- **TLS enforced** — SMTP connection uses STARTTLS.
- **Tool-call noise stripped** — Copilot CLI debug lines are removed from the report before emailing/saving; full raw output is preserved in logs for debugging.

---

## Security Notes

- `.gitignore` excludes `.env`, `__pycache__/`, `*.pyc`, and common editor/OS files.
  It does **not** exclude `*.json` — add your service account key file manually if
  stored inside the repo directory.
- **No hardcoded credentials exist in the codebase.** The tool exits immediately with a
  clear error if `SENDER_EMAIL`, `SENDER_PASSWORD`, `RECIPIENT_EMAIL`, or
  `GOOGLE_SERVICE_ACCOUNT_JSON` are not set.
- Gmail App Passwords are 16 characters without spaces. Do not use your main account password.
- `PERPLEXITY_API_KEY` and `GOOGLE_DRIVE_FOLDER_ID` are optional — the tool runs without them.
- Never commit your service account JSON key file to version control.
- Log files under `logs/` contain company names and full AI analysis output —
  treat them as sensitive if sharing logs externally.

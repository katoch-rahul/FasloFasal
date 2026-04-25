# fasalrin.gov.in claim approval automation

Automates the **REVIEW → Approve → Confirm → OK** workflow on
`https://fasalrin.gov.in/claim-application-list`.

You log in once manually; the script handles the repetitive clicking.

## One-time setup

Open a terminal in this folder and run:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

## Running

```bash
.venv\Scripts\activate
python approve_claims.py
```

A Chromium window opens. If it's your first run (or the session expired),
log in to the portal manually. Once you can see the claim list table,
return to the terminal and press **Enter**. The script then walks the
table, processing up to `MAX_RECORDS_PER_RUN` records (default 50).

The browser profile is saved in `browser-profile/` so subsequent runs
skip the login step until the portal session expires.

## Recommended first-run flow

1. Open [config.py](config.py) and confirm `DRY_RUN = True`.
2. Run the script. Watch the browser. It should click REVIEW on each row
   and return to the list, but **not** click Approve.
3. If the REVIEW click misses, right-click the real button in the
   browser → **Inspect** → copy a snippet, share it, and we'll update the
   selector in `config.py`.
4. Once the dry run looks correct, set `DRY_RUN = False` and
   `MAX_RECORDS_PER_RUN = 1`. Run on a single record. Verify in the
   portal UI that approval actually happened.
5. Raise `MAX_RECORDS_PER_RUN` to your real batch size.

## Config knobs ([config.py](config.py))

| Setting | Default | Purpose |
|---|---|---|
| `DRY_RUN` | `True` | Click REVIEW only; never Approve |
| `MAX_RECORDS_PER_RUN` | `50` | Hard cap, prevents runaways |
| `PER_RECORD_TIMEOUT_MS` | `30000` | Per-action timeout |
| `DELAY_BETWEEN_RECORDS_SEC` | `1.5` | Politeness delay |
| `SELECTORS` | placeholders | Update after first inspect |

## Output

- `logs/run_<timestamp>.csv` — one row per record with status & error
- `logs/error_*.png` — full-page screenshot whenever a record fails

Both `logs/` and `browser-profile/` are gitignored.

## Stopping

Press **Ctrl+C** in the terminal at any time. The browser stays open and
the CSV is flushed after each record, so nothing is lost.

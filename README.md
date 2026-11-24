# Web ERP automation showcase (Playwright + Python)

**Automating data entry and reconciliation in a browser-only ERP that has no API, no stable element ids and no undo.**

At my finance day job I automated document entry in a closed web accounting ERP: supplier invoices and service acts, financial commitments, payment orders, bank-statement import, downloading attachments, and evening reconciliation against the trial balance. That work grew to about 20 scripts and several hundred checks, and it runs on real documents every day.

That code and its data are private. This repository rebuilds the core techniques against **LedgerWeb**, a small mock ERP that copies the hard parts of the real one, so you can run everything locally.

> No employer code, data, names or URLs are in this repo. All contracts, suppliers and amounts are invented.

## The hard parts, and how the bot handles them

| Problem in the real ERP | What the bot does | Where |
|---|---|---|
| Field ids are regenerated on every render | Finds every input through its visible label | `ErpBot.field()` |
| A code picker selects the **first suggestion that merely contains** the typed text, so typing `6210` silently picks `6100.120` | Never trusts Enter: reads the value back, walks the list until the right code is selected, fails loudly otherwise | `ErpBot.choose_code()` |
| A bare value left in the picker looks right but is not a real selection | Accepts only a full `<code> <name>` selection | same |
| Numeric fields drop characters when typed key by key | Pastes the whole amount, then reads it back | `ErpBot.set_amount()` |
| The ERP happily saves the same document twice | Journal of entered documents works as a duplicate guard, so a re-run after a crash is safe | `Journal.already_entered()` |
| A long run can break in the middle | Each document is entered in steps saved to `progress.json` | `ErpBot._mark()` |
| A wrong posting is expensive to reverse | Every invoice is checked against the reference base **before** entry: contract, supplier, budget code, remaining contract balance across the whole batch, duplicates | `recon/precheck.py` |
| People also key documents in by hand | Evening check compares the bot journal with the ERP ledger: missing, duplicate, amount or code differences, manual entries; Excel report with problems highlighted | `recon/day_check.py` |
| You log in by hand (2FA, certificates) | `--cdp` attaches to a Chrome you already logged into | `erp_bot/run.py` |

## Run it

```bash
pip install -r requirements.txt
python -m playwright install chromium

python -m pytest -q                      # 18 tests: unit + end-to-end in a real browser

python app/server.py &                   # mock ERP on http://127.0.0.1:5055
python -m erp_bot.run data/batch_demo.json
python -m recon.day_check out/journal.csv ledger.csv day_check.xlsx   # ledger.csv from /export/ledger.csv
```

The demo batch has five invoices and is meant to show the safety net: two are entered; precheck blocks a wrong budget code, a contract that would go over its balance, and a duplicate. Run it again and nothing is entered twice.

## What the tests cover

- `test_precheck.py`: each precheck rule, including a contract balance that is fine per invoice but exceeded by the batch.
- `test_day_check.py`: every reconciliation status, cent rounding, and the Excel highlighting.
- `test_e2e_bot.py`: in a real browser, field ids really change between renders; the naive "type and press Enter" picks the wrong code (the trap is documented by a test); the bot corrects it; an unknown code fails loudly; the server's validation errors surface; a full batch run, a safe re-run, and an evening check that catches a manual entry.

Two of these tests failed on the first run and exposed real bugs in the bot: a bare typed code was accepted as a selection, and a duplicate in the batch blocked the first copy as well as the second. Both are fixed and stay covered.

## Structure

```
app/        LedgerWeb mock ERP (Flask + plain JS)
erp_bot/    Playwright bot, batch runner, journal
recon/      precheck before entry, evening reconciliation
tests/      pytest unit + end-to-end tests
data/       invented reference base and demo batch
```

## About me

Illia Baltin, QA engineer (7+ years, fintech and billing) with a Master's in finance. I test APIs, MCP servers and web apps, and automate spreadsheet and ERP routines. Available for freelance work on [Upwork](https://www.upwork.com/) and [Fiverr](https://www.fiverr.com/illiabaltin).

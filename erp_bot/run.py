"""Enter a batch of invoices: precheck -> skip duplicates -> enter step by step -> journal.

    python -m erp_bot.run data/batch_demo.json --base http://127.0.0.1:5055
    python -m erp_bot.run batch.json --cdp http://localhost:9222   # attach to a Chrome you already logged into
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright

from erp_bot.bot import EntryError, ErpBot, Invoice
from erp_bot.journal import Journal
from recon.precheck import load_reference, precheck


def run_batch(page, base: str, batch: list[dict], ref_path: Path, workdir: Path) -> dict:
    findings = precheck(batch, load_reference(ref_path))
    blocked = {f["index"] for f in findings}  # by position: a duplicate blocks only the 2nd copy
    journal = Journal(workdir / "journal.csv")
    bot = ErpBot(page, base, progress_file=workdir / "progress.json")
    result = {"entered": [], "skipped": [], "blocked": findings, "failed": []}
    for i, d in enumerate(batch):
        inv = Invoice.from_dict(d)
        tag = f"{inv.contract} / {inv.doc_no}"
        if i in blocked:
            continue
        if journal.already_entered(inv.contract, inv.doc_no):
            result["skipped"].append(tag)
            continue
        try:
            erp_id = bot.enter_invoice(inv)
            journal.add(inv, erp_id, "saved")
            result["entered"].append({"doc": tag, "erp_id": erp_id})
        except EntryError as e:
            journal.add(inv, None, f"failed: {e}")
            result["failed"].append({"doc": tag, "error": str(e)})
    return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("batch")
    ap.add_argument("--base", default="http://127.0.0.1:5055")
    ap.add_argument("--ref", default="data/reference.csv")
    ap.add_argument("--workdir", default="out")
    ap.add_argument("--cdp", help="attach to an existing Chrome started with --remote-debugging-port")
    ap.add_argument("--headed", action="store_true")
    a = ap.parse_args()
    work = Path(a.workdir)
    work.mkdir(exist_ok=True)
    batch = json.loads(Path(a.batch).read_text(encoding="utf-8"))
    with sync_playwright() as p:
        if a.cdp:
            browser = p.chromium.connect_over_cdp(a.cdp)
            page = browser.contexts[0].new_page()
        else:
            browser = p.chromium.launch(headless=not a.headed,
                                        executable_path=os.environ.get("CHROME_PATH") or None)
            page = browser.new_page()
        print(json.dumps(run_batch(page, a.base, batch, Path(a.ref), work), indent=2))
        browser.close()


if __name__ == "__main__":
    main()

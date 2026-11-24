"""End-to-end: the bot drives the mock ERP in a real browser."""
import json
import re
from pathlib import Path

import pytest
from playwright.sync_api import expect

from erp_bot.bot import EntryError, ErpBot, Invoice
from erp_bot.run import run_batch
from recon.day_check import compare

ROOT = Path(__file__).resolve().parents[1]


def test_field_ids_change_between_renders(page, erp):
    _, base = erp
    page.goto(base + "/doc/new?contract=C-101")
    first = page.locator("label", has_text="Amount").get_attribute("for")
    page.reload()
    assert page.locator("label", has_text="Amount").get_attribute("for") != first


def test_naive_enter_picks_the_wrong_code(page, erp):
    """Documents the trap: typing the code and pressing Enter is not enough."""
    _, base = erp
    page.goto(base + "/doc/new?contract=C-101")
    bot = ErpBot(page, base)
    f = bot.field("Budget code")
    f.type("6210")
    f.press("Enter")
    assert f.input_value().startswith("6100.120")


def test_bot_verifies_and_corrects_the_code(page, erp):
    _, base = erp
    page.goto(base + "/doc/new?contract=C-101")
    bot = ErpBot(page, base)
    bot.choose_code("Budget code", "6210.600")
    assert bot.field("Budget code").input_value().startswith("6210.600")


def test_unknown_code_fails_loudly(page, erp):
    _, base = erp
    page.goto(base + "/doc/new?contract=C-101")
    with pytest.raises(EntryError, match="could not select 9999"):
        ErpBot(page, base).choose_code("Budget code", "9999")


def test_server_rejects_missing_fields(page, erp):
    _, base = erp
    page.goto(base + "/doc/new?contract=C-101")
    with pytest.raises(EntryError, match="Required: Document №, Date, Amount, Budget code"):
        ErpBot(page, base).save()


def test_enter_one_invoice(page, erp):
    app, base = erp
    doc_id = ErpBot(page, base).enter_invoice(
        Invoice("C-101", "INV-5521", "2026-10-21", 9875.4, "6210.600"))
    expect(page.locator("#status")).to_have_text(re.compile(rf"Saved: document {doc_id}"))
    saved = app.config["DOCS"][-1]
    assert (saved["doc_no"], saved["amount"], saved["budget_code"]) == ("INV-5521", 9875.4, "6210.600")


def test_batch_run_then_rerun_and_evening_check(page, erp, tmp_path):
    app, base = erp
    batch = json.loads((ROOT / "data/batch_demo.json").read_text())

    r1 = run_batch(page, base, batch, ROOT / "data/reference.csv", tmp_path)
    assert [e["doc"] for e in r1["entered"]] == ["C-101 / INV-5521", "C-205 / SV-1182"]
    assert len(r1["blocked"]) == 3 and r1["failed"] == []

    # Re-running the same batch (e.g. after a crash) must not create duplicates.
    r2 = run_batch(page, base, batch, ROOT / "data/reference.csv", tmp_path)
    assert r2["entered"] == [] and r2["skipped"] == ["C-101 / INV-5521", "C-205 / SV-1182"]
    assert len(app.config["DOCS"]) == 2

    # Someone also keys a document in by hand; the evening check must notice it.
    app.config["DOCS"].append({"id": 9, "contract": "C-205", "doc_no": "SV-9001", "amount": 10.0,
                               "budget_code": "6260.480"})
    journal = (tmp_path / "journal.csv").read_text().splitlines()
    import csv
    rows = compare(list(csv.DictReader(journal)),
                   [{k: str(v) for k, v in d.items()} for d in app.config["DOCS"]])
    assert {r["doc_no"]: r["status"] for r in rows} == {
        "INV-5521": "OK", "SV-1182": "OK", "SV-9001": "In ERP, not in journal (manual entry?)"}

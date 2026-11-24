"""Playwright bot for a web ERP that has no API and no stable element ids."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from playwright.sync_api import Page, expect


class EntryError(RuntimeError):
    """The ERP did not accept a value or a document; the step can be retried."""


@dataclass
class Invoice:
    contract: str
    doc_no: str
    date: str
    amount: float
    budget_code: str
    supplier: str = ""

    @classmethod
    def from_dict(cls, d: dict) -> "Invoice":
        return cls(**{k: d[k] for k in cls.__dataclass_fields__ if k in d})


class ErpBot:
    """Every shared action lives here; scripts for other document types import it."""

    def __init__(self, page: Page, base_url: str, progress_file: Path | None = None):
        self.page = page
        self.base = base_url.rstrip("/")
        self.progress_file = progress_file
        self.progress: dict = {}
        if progress_file and progress_file.exists():
            self.progress = json.loads(progress_file.read_text(encoding="utf-8"))

    # ---------- finding things ----------
    def field(self, label: str):
        """Ids change on every render, labels do not: resolve the input through its <label for>."""
        lab = self.page.locator("label", has_text=re.compile(rf"^\s*{re.escape(label)}\s*$"))
        if lab.count() != 1:
            raise EntryError(f"label '{label}' found {lab.count()} times")
        return self.page.locator(f"#{lab.get_attribute('for')}")

    # ---------- steps ----------
    def _done(self, key: str, step: str) -> bool:
        return step in self.progress.get(key, [])

    def _mark(self, key: str, step: str) -> None:
        self.progress.setdefault(key, []).append(step)
        if self.progress_file:
            self.progress_file.write_text(json.dumps(self.progress, indent=2), encoding="utf-8")

    def open_contract(self, contract: str) -> None:
        self.page.goto(self.base + "/")
        self.field("Contract №").fill(contract)
        self.page.click("#BTN_FILTER")
        row = self.page.locator(f"tr[data-contract='{contract}']")
        expect(row).to_have_count(1)
        row.locator("a.create").click()
        expect(self.page.locator("h1")).to_contain_text(contract)

    def set_amount(self, value: float) -> None:
        # Numeric fields in the real system lose characters when typed key by key, so paste the whole value.
        f = self.field("Amount")
        f.fill(f"{value:.2f}")
        if float(f.input_value()) != round(value, 2):
            raise EntryError(f"Amount shows {f.input_value()}, expected {value:.2f}")

    def choose_code(self, label: str, code: str, attempts: int = 6) -> None:
        """Type the code, press Enter, then CHECK what was really selected.

        The picker takes the first suggestion that merely contains the text, so the
        first Enter may land on the wrong code. Walk the list until the value is right.
        """
        f = self.field(label)
        for i in range(attempts):
            f.fill("")
            f.type(code)
            for _ in range(i):
                f.press("ArrowDown")
            f.press("Enter")
            # A bare "9999" left in the box is NOT a selection: a picked item reads "<code> <name>".
            if f.input_value().startswith(code + " "):
                return
        raise EntryError(f"{label}: could not select {code}, field shows '{f.input_value()}'")

    def save(self) -> int:
        self.page.click("#BTN_SAVE")
        status = self.page.locator("#status")
        expect(status).not_to_be_empty()
        text = status.inner_text()
        m = re.search(r"Saved: document (\d+)", text)
        if not m:
            raise EntryError(text)
        return int(m.group(1))

    def enter_invoice(self, inv: Invoice) -> int:
        key = f"{inv.contract}|{inv.doc_no}"
        self.open_contract(inv.contract)
        self.field("Document №").fill(inv.doc_no)
        self.field("Date").fill(inv.date)
        self.set_amount(inv.amount)
        self.choose_code("Budget code", inv.budget_code)
        self._mark(key, "filled")
        doc_id = self.save()
        self._mark(key, f"saved:{doc_id}")
        return doc_id

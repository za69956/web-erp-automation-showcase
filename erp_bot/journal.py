"""Journal of entered documents. It doubles as the duplicate guard: the ERP itself happily saves duplicates."""
from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

FIELDS = ["when", "contract", "doc_no", "amount", "budget_code", "erp_id", "status"]


class Journal:
    def __init__(self, path: Path):
        self.path = path
        if not path.exists():
            with path.open("w", newline="", encoding="utf-8") as f:
                csv.DictWriter(f, fieldnames=FIELDS).writeheader()

    def rows(self) -> list[dict]:
        with self.path.open(newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))

    def already_entered(self, contract: str, doc_no: str) -> bool:
        return any(r["contract"] == contract and r["doc_no"] == doc_no and r["status"] == "saved"
                   for r in self.rows())

    def add(self, inv, erp_id: int | None, status: str) -> None:
        with self.path.open("a", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=FIELDS).writerow({
                "when": datetime.now().isoformat(timespec="seconds"),
                "contract": inv.contract, "doc_no": inv.doc_no, "amount": f"{inv.amount:.2f}",
                "budget_code": inv.budget_code, "erp_id": erp_id or "", "status": status,
            })

"""Check every invoice against the reference base BEFORE it goes into the ERP.

A wrong document is cheap to stop here and expensive to reverse after posting.
"""
from __future__ import annotations

import csv
from pathlib import Path


def load_reference(path: Path) -> dict[str, dict]:
    with path.open(newline="", encoding="utf-8") as f:
        return {r["contract"]: {**r, "remaining": float(r["remaining"])} for r in csv.DictReader(f)}


def precheck(invoices: list[dict], ref: dict[str, dict]) -> list[dict]:
    """Return one finding per problem; an empty list means the batch is safe to enter."""
    findings = []
    seen = set()
    spent: dict[str, float] = {}
    for i, inv in enumerate(invoices):
        key = (inv["contract"], inv["doc_no"])
        tag = f'{inv["contract"]} / {inv["doc_no"]}'
        if key in seen:
            findings.append({"index": i, "doc": tag, "problem": "duplicate in this batch"})
            continue
        seen.add(key)
        c = ref.get(inv["contract"])
        if c is None:
            findings.append({"index": i, "doc": tag, "problem": "contract not in reference base"})
            continue
        if inv.get("supplier") and inv["supplier"] != c["supplier"]:
            findings.append({"index": i, "doc": tag, "problem": f'supplier "{inv["supplier"]}" != contract supplier "{c["supplier"]}"'})
        if inv["budget_code"] != c["budget_code"]:
            findings.append({"index": i, "doc": tag, "problem": f'budget code {inv["budget_code"]} not allowed (contract uses {c["budget_code"]})'})
        if inv["amount"] <= 0:
            findings.append({"index": i, "doc": tag, "problem": "amount must be positive"})
        spent[inv["contract"]] = spent.get(inv["contract"], 0) + inv["amount"]
        if spent[inv["contract"]] > c["remaining"] + 0.005:
            findings.append({"index": i, "doc": tag, "problem": f'contract balance exceeded: {spent[inv["contract"]]:.2f} > {c["remaining"]:.2f}'})
    return findings

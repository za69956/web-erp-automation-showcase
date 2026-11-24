"""Evening check: what the bot says it entered vs what the ERP ledger really contains."""
from __future__ import annotations

import csv
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill


def read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def compare(journal: list[dict], ledger: list[dict]) -> list[dict]:
    saved = [r for r in journal if r["status"] == "saved"]
    j = {(r["contract"], r["doc_no"]): r for r in saved}
    led: dict[tuple, list[dict]] = {}
    for r in ledger:
        led.setdefault((r["contract"], r["doc_no"]), []).append(r)
    out = []
    for key in sorted(set(j) | set(led)):
        jr, lr = j.get(key), led.get(key, [])
        row = {"contract": key[0], "doc_no": key[1],
               "journal_amount": float(jr["amount"]) if jr else None,
               "ledger_amount": sum(float(x["amount"]) for x in lr) if lr else None}
        if jr and not lr:
            row["status"] = "MISSING in ERP"
        elif lr and not jr:
            row["status"] = "In ERP, not in journal (manual entry?)"
        elif len(lr) > 1:
            row["status"] = f"DUPLICATE in ERP ({len(lr)} copies)"
        elif abs(row["journal_amount"] - row["ledger_amount"]) > 0.005:
            row["status"] = "AMOUNT differs"
        elif jr["budget_code"] != lr[0]["budget_code"]:
            row["status"] = f'BUDGET CODE differs ({jr["budget_code"]} vs {lr[0]["budget_code"]})'
        else:
            row["status"] = "OK"
        out.append(row)
    return out


def write_report(rows: list[dict], path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Day check"
    head = ["contract", "doc_no", "journal_amount", "ledger_amount", "status"]
    ws.append(head)
    for c in ws[1]:
        c.font = Font(bold=True)
    bad = PatternFill("solid", fgColor="F8D7DA")
    for r in rows:
        ws.append([r[h] for h in head])
        if r["status"] != "OK":
            for c in ws[ws.max_row]:
                c.fill = bad
    ws.column_dimensions["E"].width = 40
    wb.save(path)


if __name__ == "__main__":
    import sys
    rows = compare(read_csv(Path(sys.argv[1])), read_csv(Path(sys.argv[2])))
    write_report(rows, Path(sys.argv[3] if len(sys.argv) > 3 else "day_check.xlsx"))
    print(*(f'{r["contract"]:8} {r["doc_no"]:10} {r["status"]}' for r in rows), sep="\n")

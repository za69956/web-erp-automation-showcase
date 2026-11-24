from openpyxl import load_workbook

from recon.day_check import compare, write_report


def j(contract, doc, amount, code="6210.600", status="saved"):
    return {"contract": contract, "doc_no": doc, "amount": str(amount), "budget_code": code, "status": status}


def l(contract, doc, amount, code="6210.600"):
    return {"contract": contract, "doc_no": doc, "amount": str(amount), "budget_code": code}


def statuses(journal, ledger):
    return {r["doc_no"]: r["status"] for r in compare(journal, ledger)}


def test_all_statuses():
    journal = [j("1", "ok", 10), j("1", "miss", 10), j("1", "amt", 10), j("1", "dup", 10),
               j("1", "code", 10), j("1", "failed", 10, status="failed: x")]
    ledger = [l("1", "ok", 10), l("1", "amt", 11), l("1", "dup", 10), l("1", "dup", 10),
              l("1", "code", 10, code="6100.120"), l("1", "manual", 5)]
    s = statuses(journal, ledger)
    assert s == {
        "ok": "OK",
        "miss": "MISSING in ERP",
        "amt": "AMOUNT differs",
        "dup": "DUPLICATE in ERP (2 copies)",
        "code": "BUDGET CODE differs (6210.600 vs 6100.120)",
        "manual": "In ERP, not in journal (manual entry?)",
    }


def test_cent_rounding_is_not_a_mismatch():
    assert statuses([j("1", "a", 0.1 + 0.2)], [l("1", "a", 0.3)])["a"] == "OK"


def test_report_highlights_problems(tmp_path):
    p = tmp_path / "r.xlsx"
    write_report(compare([j("1", "a", 1), j("1", "b", 1)], [l("1", "a", 1)]), p)
    ws = load_workbook(p).active
    assert ws["E2"].value == "OK" and ws["E3"].value == "MISSING in ERP"
    assert ws["E3"].fill.fgColor.rgb.endswith("F8D7DA")

import json
from pathlib import Path

from recon.precheck import load_reference, precheck

ROOT = Path(__file__).resolve().parents[1]
REF = load_reference(ROOT / "data/reference.csv")


def inv(**kw):
    base = {"contract": "C-101", "doc_no": "1", "date": "2026-10-01", "amount": 100.0,
            "budget_code": "6210.600", "supplier": "Northwind Building Supply"}
    base.update(kw)
    return base


def test_clean_invoice_passes():
    assert precheck([inv()], REF) == []


def test_unknown_contract():
    assert precheck([inv(contract="99/999")], REF)[0]["problem"] == "contract not in reference base"


def test_wrong_supplier():
    assert "supplier" in precheck([inv(supplier="Someone Else")], REF)[0]["problem"]


def test_wrong_budget_code():
    assert "budget code 6100.120 not allowed" in precheck([inv(budget_code="6100.120")], REF)[0]["problem"]


def test_duplicate_inside_batch():
    f = precheck([inv(), inv()], REF)
    assert [x["problem"] for x in f] == ["duplicate in this batch"]


def test_contract_balance_counts_the_whole_batch():
    # C-102 has 4000 left: each invoice fits alone, together they do not.
    f = precheck([inv(contract="C-102", doc_no="a", amount=2500),
                  inv(contract="C-102", doc_no="b", amount=2500)], REF)
    assert len(f) == 1 and "balance exceeded: 5000.00 > 4000.00" in f[0]["problem"]


def test_non_positive_amount():
    assert precheck([inv(amount=0)], REF)[0]["problem"] == "amount must be positive"


def test_demo_batch_findings():
    batch = json.loads((ROOT / "data/batch_demo.json").read_text())
    problems = sorted(f["problem"] for f in precheck(batch, REF))
    assert problems == [
        "budget code 6210.600 not allowed (contract uses 6240.400)",
        "contract balance exceeded: 4620.00 > 4000.00",
        "duplicate in this batch",
    ]

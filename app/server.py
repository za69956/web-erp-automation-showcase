"""LedgerWeb: a small mock of a closed web ERP, used as the test target.

It copies the awkward parts of the real thing on purpose:
- field ids are random on every render, so a bot must find fields by their labels;
- the budget-code picker selects the FIRST suggestion that contains the typed text,
  so typing "6210" can silently pick a different code;
- the server accepts duplicate documents, so duplicate protection is the bot's job;
- the page talks to the server through one generic endpoint (/api/request).
"""
from __future__ import annotations

import csv
import io
import itertools
import uuid
from datetime import date

from flask import Flask, Response, jsonify, render_template, request

BUDGET_CODES = [
    ("6100.120", "Payroll accruals (incl. 6210 staff)"),
    ("6210.100", "Office supplies"),
    ("6210.600", "Construction materials"),
    ("6240.400", "Vehicle maintenance services"),
    ("6260.480", "Waste removal services"),
]

CONTRACTS = {
    "C-101": {"supplier": "Northwind Building Supply", "budget_code": "6210.600"},
    "C-102": {"supplier": "Northwind Building Supply", "budget_code": "6210.600"},
    "C-205": {"supplier": "CleanCity Services", "budget_code": "6260.480"},
    "C-310": {"supplier": "TruckCare Ltd", "budget_code": "6240.400"},
}


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["DOCS"] = []
    ids = itertools.count(1001)

    def rid() -> str:
        return "dhx_" + uuid.uuid4().hex[:8]

    @app.get("/")
    def contracts():
        q = request.args.get("q", "").strip()
        rows = {k: v for k, v in CONTRACTS.items() if q in k}
        return render_template("contracts.html", rows=rows, q=q, filter_id=rid())

    @app.get("/doc/new")
    def new_doc():
        no = request.args.get("contract", "")
        if no not in CONTRACTS:
            return "Unknown contract", 404
        fields = {name: rid() for name in
                  ["Document №", "Date", "Supplier", "Amount", "Budget code"]}
        return render_template("doc.html", contract=no, c=CONTRACTS[no],
                               fields=fields, codes=BUDGET_CODES)

    @app.post("/api/request")
    def api_request():
        body = request.get_json(force=True)
        values = {e["control"]: e["value"] for e in body.get("events", [])}
        missing = [k for k in ["Document №", "Date", "Amount", "Budget code"] if not values.get(k)]
        if missing:
            return jsonify(ok=False, error=f"Required: {', '.join(missing)}"), 422
        try:
            amount = round(float(str(values["Amount"]).replace(" ", "").replace(",", ".")), 2)
        except ValueError:
            return jsonify(ok=False, error="Amount is not a number"), 422
        doc = {
            "id": next(ids),
            "contract": body["contract"],
            "doc_no": values["Document №"],
            "date": values["Date"],
            "supplier": values.get("Supplier", ""),
            "amount": amount,
            "budget_code": values["Budget code"].split(" ")[0],
            "saved_on": date.today().isoformat(),
        }
        app.config["DOCS"].append(doc)
        return jsonify(ok=True, id=doc["id"])

    @app.get("/api/docs")
    def docs():
        return jsonify(app.config["DOCS"])

    @app.get("/export/ledger.csv")
    def ledger():
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=["id", "contract", "doc_no", "date",
                                            "supplier", "amount", "budget_code", "saved_on"])
        w.writeheader()
        w.writerows(app.config["DOCS"])
        return Response(buf.getvalue(), mimetype="text/csv")

    @app.post("/api/reset")
    def reset():
        app.config["DOCS"].clear()
        return jsonify(ok=True)

    return app


if __name__ == "__main__":
    create_app().run(port=5055, debug=False)

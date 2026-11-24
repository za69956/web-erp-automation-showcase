import os
import sys
import threading
from pathlib import Path

import pytest
from werkzeug.serving import make_server

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.server import create_app  # noqa: E402


@pytest.fixture(scope="session")
def erp():
    app = create_app()
    srv = make_server("127.0.0.1", 0, app)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield app, f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()


@pytest.fixture()
def page(erp):
    from playwright.sync_api import sync_playwright
    app, _ = erp
    app.config["DOCS"].clear()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, executable_path=os.environ.get("CHROME_PATH") or None)
        pg = browser.new_page()
        pg.set_default_timeout(5000)
        yield pg
        browser.close()

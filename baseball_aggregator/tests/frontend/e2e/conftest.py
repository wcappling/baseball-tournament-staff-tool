"""Pytest fixtures for Playwright E2E tests.

Spins up a real uvicorn server with DEV_AUTO_LOGIN=true and a
temp SQLite directory, then tears it down after the session.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx
import pytest

PORT = 18765
BASE_URL = f"http://localhost:{PORT}"


@pytest.fixture(scope="session")
def live_server():
    data_dir = tempfile.mkdtemp(prefix="tiq_e2e_")
    env = {
        **os.environ,
        "DEV_AUTO_LOGIN": "true",
        "STAFF_TOOL_DATA_DIR": data_dir,
    }
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "baseball_aggregator.app:app",
         "--host", "127.0.0.1", "--port", str(PORT)],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    # Poll until the server accepts connections (up to 15 s)
    deadline = time.time() + 15
    while time.time() < deadline:
        try:
            httpx.get(f"{BASE_URL}/static/index.html", timeout=1).raise_for_status()
            break
        except Exception:
            time.sleep(0.3)
    else:
        proc.terminate()
        raise RuntimeError("Test server did not start in time")

    yield BASE_URL

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


@pytest.fixture(scope="session")
def browser_context(playwright, live_server):
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context(base_url=live_server)
    yield context
    context.close()
    browser.close()


@pytest.fixture
def page(browser_context):
    pg = browser_context.new_page()
    yield pg
    pg.close()

"""Headless smoke test of the full Streamlit app via Streamlit's AppTest.

Runs app.py end-to-end (auth gate -> login -> every page) against an isolated
temporary database, asserting that no page raises. This is the integration
safety net for the views/ package split.
"""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parent.parent / "app.py")
PAGES = ["Schedule", "Employees", "Shift Templates", "Payroll", "Settings"]


def _is_authed(at: AppTest) -> bool:
    return "authenticated" in at.session_state and at.session_state["authenticated"]


def _start_authenticated(temp_db) -> AppTest:
    at = AppTest.from_file(APP)
    at.secrets["password"] = "test"
    at.run()
    at.text_input(key="login_password").set_value("test")
    at.button[0].click().run()
    return at


def test_auth_gate_blocks_then_allows(temp_db):
    at = AppTest.from_file(APP)
    at.secrets["password"] = "test"
    at.run()
    assert not at.exception
    assert not _is_authed(at)

    at.text_input(key="login_password").set_value("test")
    at.button[0].click().run()
    assert _is_authed(at)


def test_wrong_password_is_rejected(temp_db):
    at = AppTest.from_file(APP)
    at.secrets["password"] = "correct-horse"
    at.run()
    at.text_input(key="login_password").set_value("wrong")
    at.button[0].click().run()
    assert not _is_authed(at)


@pytest.mark.parametrize("page", PAGES)
def test_each_page_renders_without_error(temp_db, page):
    at = _start_authenticated(temp_db)
    at.sidebar.radio[0].set_value(page).run()
    assert not at.exception, f"{page} page raised: {at.exception}"

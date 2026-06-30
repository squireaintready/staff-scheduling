"""Headless smoke test of the full Streamlit app via Streamlit's AppTest.

Runs app.py end-to-end (auth gate -> login -> every page) against an isolated
temporary database, asserting that no page raises. This is the integration
safety net for the views/ package split.
"""

from datetime import date
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parent.parent / "app.py")
PAGES = ["Schedule", "Employees", "Shift Templates", "Payroll", "Settings"]


def _is_authed(at: AppTest) -> bool:
    return "authenticated" in at.session_state and at.session_state["authenticated"]


def _start_authenticated(temp_db, demo_mode=False) -> AppTest:
    # demo seeding defaults to ON in the app, so disable it here unless a test
    # explicitly wants the sample data — keeps page tests on a known empty DB.
    at = AppTest.from_file(APP)
    at.secrets["password"] = "test"
    at.secrets["demo_mode"] = demo_mode
    at.run()
    at.text_input(key="login_password").set_value("test")
    at.button[0].click().run()
    return at


def test_auth_gate_blocks_then_allows(temp_db):
    at = AppTest.from_file(APP)
    at.secrets["password"] = "test"
    at.secrets["demo_mode"] = False
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


def test_payroll_report_renders_with_seeded_data(temp_db):
    # Seed a shift in the current week so the default weekly report has content,
    # exercising the By-Role table, the pay-distribution chart, and exports.
    emp = temp_db.add_employee("Reporter", 20.0, role="Server")
    temp_db.add_shift(emp, date.today().isoformat(), "09:00", "17:00", "12:00", "13:00")

    at = _start_authenticated(temp_db)
    at.sidebar.radio[0].set_value("Payroll").run()
    generate = next(b for b in at.button if b.label == "Generate Report")
    generate.click().run()

    assert not at.exception
    assert "payroll_report" in at.session_state


def test_seeds_by_default_when_empty(temp_db):
    # No demo_mode secret -> seeding is on by default, so an empty DB fills.
    at = AppTest.from_file(APP)
    at.secrets["password"] = "test"
    at.run()
    at.text_input(key="login_password").set_value("test")
    at.button[0].click().run()
    assert not at.exception
    assert len(temp_db.get_employees(active_only=False)) == 8


def test_demo_mode_false_disables_seeding(temp_db):
    # demo_mode = false opts a real deployment out of auto-seeding.
    _start_authenticated(temp_db, demo_mode=False)
    assert temp_db.get_employees(active_only=False) == []

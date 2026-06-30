"""End-to-end payroll tests that exercise the full pipeline:
seed employees + shifts in SQLite -> compute a payroll report.

This is where the calculation engine and the data layer meet, so it catches
wiring bugs that the isolated unit tests cannot.
"""

import payroll as pr


def test_report_totals_match_seeded_shifts(temp_db):
    alice = temp_db.add_employee("Alice", 20.0)
    bob = temp_db.add_employee("Bob", 15.0)

    # Alice: Mon-Fri, 9-5 with a 1h lunch = 7h/day x 5 = 35h, all regular.
    for day in range(19, 24):  # 2026-01-19 (Mon) .. 2026-01-23 (Fri)
        temp_db.add_shift(alice, f"2026-01-{day}", "09:00", "17:00", "12:00", "13:00")

    # Bob: a single 10h day -> 8h regular + 2h overtime (daily rule).
    temp_db.add_shift(bob, "2026-01-19", "08:00", "18:00")

    report = pr.calculate_payroll_report("2026-01-19", "2026-01-25")
    by_name = {e.employee_name: e for e in report["employees"]}

    assert by_name["Alice"].total_hours == 35.0
    assert by_name["Alice"].total_overtime_hours == 0.0
    assert by_name["Alice"].total_pay == 35.0 * 20.0

    assert by_name["Bob"].total_regular_hours == 8.0
    assert by_name["Bob"].total_overtime_hours == 2.0
    # 8h @ $15 + 2h @ $15 * 1.5 = 120 + 45 = 165
    assert by_name["Bob"].total_pay == 165.0

    assert report["summary"]["total_hours"] == 45.0
    assert report["summary"]["total_pay"] == 35.0 * 20.0 + 165.0


def test_overtime_settings_are_respected(temp_db):
    emp = temp_db.add_employee("Henry", 10.0)
    temp_db.add_shift(emp, "2026-01-19", "08:00", "18:00")  # 10h day

    # Lower the daily overtime threshold to 6h: now 6h regular + 4h OT.
    temp_db.set_setting("overtime_daily_threshold", "6")

    report = pr.calculate_payroll_report("2026-01-19", "2026-01-25")
    henry = report["employees"][0]
    assert henry.total_regular_hours == 6.0
    assert henry.total_overtime_hours == 4.0
    # 6 @ $10 + 4 @ $10 * 1.5 = 60 + 60 = 120
    assert henry.total_pay == 120.0
